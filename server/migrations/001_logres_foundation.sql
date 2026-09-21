CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- MASTER DATA
-- =========================================================

CREATE TABLE IF NOT EXISTS game_jobs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (
    role IN ('damage', 'tank', 'support', 'healer')
  ),
  hp INTEGER NOT NULL CHECK (hp > 0),
  physical_attack INTEGER NOT NULL CHECK (physical_attack >= 0),
  magical_attack INTEGER NOT NULL CHECK (magical_attack >= 0),
  physical_defense INTEGER NOT NULL CHECK (physical_defense >= 0),
  magical_defense INTEGER NOT NULL CHECK (magical_defense >= 0),
  provenance TEXT NOT NULL CHECK (
    provenance IN (
      'extracted',
      'confirmed',
      'inferred',
      'reconstructed',
      'original'
    )
  ),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS game_items (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (
    category IN (
      'material',
      'consumable',
      'weapon',
      'armor',
      'accessory',
      'quest'
    )
  ),
  rarity TEXT NOT NULL,
  element TEXT NOT NULL DEFAULT 'neutral',
  weapon_type TEXT,
  equipment_slot TEXT,
  stack_limit INTEGER NOT NULL DEFAULT 1
    CHECK (stack_limit > 0),
  stats JSONB NOT NULL DEFAULT '{}'::jsonb,
  provenance TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS game_skills (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  element TEXT NOT NULL,
  power NUMERIC(10,4) NOT NULL CHECK (power > 0),
  energy_cost INTEGER NOT NULL CHECK (energy_cost >= 0),
  cooldown_ms INTEGER NOT NULL CHECK (cooldown_ms >= 0),
  provenance TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS job_weapon_permissions (
  job_id TEXT NOT NULL
    REFERENCES game_jobs(id) ON DELETE CASCADE,
  weapon_type TEXT NOT NULL,
  PRIMARY KEY (job_id, weapon_type)
);

CREATE TABLE IF NOT EXISTS skill_job_permissions (
  skill_id TEXT NOT NULL
    REFERENCES game_skills(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL
    REFERENCES game_jobs(id) ON DELETE CASCADE,
  PRIMARY KEY (skill_id, job_id)
);

CREATE TABLE IF NOT EXISTS game_monsters (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  level INTEGER NOT NULL CHECK (level > 0),
  element TEXT NOT NULL,
  hp INTEGER NOT NULL CHECK (hp > 0),
  physical_attack INTEGER NOT NULL CHECK (physical_attack >= 0),
  magical_attack INTEGER NOT NULL CHECK (magical_attack >= 0),
  physical_defense INTEGER NOT NULL CHECK (physical_defense >= 0),
  magical_defense INTEGER NOT NULL CHECK (magical_defense >= 0),
  xp_reward INTEGER NOT NULL DEFAULT 0,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  provenance TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS game_drop_entries (
  id TEXT PRIMARY KEY,
  monster_id TEXT NOT NULL
    REFERENCES game_monsters(id) ON DELETE CASCADE,
  item_id TEXT NOT NULL
    REFERENCES game_items(id) ON DELETE CASCADE,
  chance NUMERIC(8,6) NOT NULL
    CHECK (chance >= 0 AND chance <= 1),
  min_quantity INTEGER NOT NULL DEFAULT 1,
  max_quantity INTEGER NOT NULL DEFAULT 1,
  provenance TEXT NOT NULL,
  CHECK (min_quantity > 0),
  CHECK (max_quantity >= min_quantity)
);

CREATE TABLE IF NOT EXISTS game_quests (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  required_level INTEGER NOT NULL DEFAULT 1,
  target_monster_id TEXT
    REFERENCES game_monsters(id),
  required_kills INTEGER,
  xp_reward INTEGER NOT NULL DEFAULT 0,
  coin_reward INTEGER NOT NULL DEFAULT 0,
  provenance TEXT NOT NULL,
  notes TEXT
);

-- =========================================================
-- PLAYERS
-- =========================================================

CREATE TABLE IF NOT EXISTS players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_uid TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  active_job_id TEXT REFERENCES game_jobs(id),
  level INTEGER NOT NULL DEFAULT 1 CHECK (level > 0),
  xp BIGINT NOT NULL DEFAULT 0 CHECK (xp >= 0),
  coins BIGINT NOT NULL DEFAULT 0 CHECK (coins >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS player_jobs (
  player_id UUID NOT NULL
    REFERENCES players(id) ON DELETE CASCADE,
  job_id TEXT NOT NULL
    REFERENCES game_jobs(id),
  level INTEGER NOT NULL DEFAULT 1 CHECK (level > 0),
  xp BIGINT NOT NULL DEFAULT 0 CHECK (xp >= 0),
  unlocked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, job_id)
);

CREATE TABLE IF NOT EXISTS player_inventory (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID NOT NULL
    REFERENCES players(id) ON DELETE CASCADE,
  item_id TEXT NOT NULL
    REFERENCES game_items(id),
  quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
  locked BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS
  idx_inventory_player
ON player_inventory(player_id);

CREATE TABLE IF NOT EXISTS player_equipment (
  player_id UUID NOT NULL
    REFERENCES players(id) ON DELETE CASCADE,
  slot TEXT NOT NULL,
  inventory_entry_id UUID NOT NULL UNIQUE
    REFERENCES player_inventory(id) ON DELETE CASCADE,
  equipped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, slot)
);

CREATE TABLE IF NOT EXISTS player_skills (
  player_id UUID NOT NULL
    REFERENCES players(id) ON DELETE CASCADE,
  skill_id TEXT NOT NULL
    REFERENCES game_skills(id),
  level INTEGER NOT NULL DEFAULT 1 CHECK (level > 0),
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, skill_id)
);

CREATE TABLE IF NOT EXISTS player_quests (
  player_id UUID NOT NULL
    REFERENCES players(id) ON DELETE CASCADE,
  quest_id TEXT NOT NULL
    REFERENCES game_quests(id),
  status TEXT NOT NULL CHECK (
    status IN ('available', 'active', 'ready', 'completed')
  ),
  progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0),
  accepted_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  PRIMARY KEY (player_id, quest_id)
);

-- =========================================================
-- AUTHORITATIVE BATTLES
-- =========================================================

CREATE TABLE IF NOT EXISTS battle_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  seed BIGINT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('forming', 'active', 'won', 'lost', 'escaped', 'closed')
  ),
  state_version BIGINT NOT NULL DEFAULT 0,
  state JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS battle_participants (
  battle_id UUID NOT NULL
    REFERENCES battle_sessions(id) ON DELETE CASCADE,
  participant_id TEXT NOT NULL,
  player_id UUID REFERENCES players(id),
  monster_id TEXT REFERENCES game_monsters(id),
  team SMALLINT NOT NULL,
  hp INTEGER NOT NULL CHECK (hp >= 0),
  energy INTEGER NOT NULL DEFAULT 0 CHECK (energy >= 0),
  status TEXT NOT NULL DEFAULT 'alive',
  PRIMARY KEY (battle_id, participant_id),
  CHECK (
    (
      player_id IS NOT NULL AND
      monster_id IS NULL
    )
    OR
    (
      player_id IS NULL AND
      monster_id IS NOT NULL
    )
  )
);

CREATE TABLE IF NOT EXISTS battle_events (
  battle_id UUID NOT NULL
    REFERENCES battle_sessions(id) ON DELETE CASCADE,
  sequence BIGINT NOT NULL,
  actor_participant_id TEXT,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (battle_id, sequence)
);

CREATE INDEX IF NOT EXISTS
  idx_battle_events_battle
ON battle_events(battle_id, sequence);

-- Prevent duplicate client mutations from granting rewards twice.
CREATE TABLE IF NOT EXISTS mutation_receipts (
  request_id TEXT PRIMARY KEY,
  player_id UUID NOT NULL
    REFERENCES players(id) ON DELETE CASCADE,
  mutation_type TEXT NOT NULL,
  result JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
