# Strict Logres Reconstruction Mode

The active game reconstruction uses the extracted
Logres clients as its source of truth.

Rules:

- No legacy Awakened Realms roguelike gameplay.
- No legacy RPG prototype content.
- No invented NPCs, monsters, jobs, skills, quests,
  items, currencies, maps, or balance values.
- Japanese Logres client is the primary reference.
- Global Logres client is the secondary reference.
- Runtime visuals use extracted Logres assets privately.
- Runtime configuration should read extracted client
  JSON directly whenever practical.
- Missing server-only values remain unknown until they
  can be reconstructed from evidence.
- Reconstructed server behavior must be explicitly
  labeled RECONSTRUCTED.
- Original future Awakened Realms content must be
  explicitly labeled ORIGINAL.
