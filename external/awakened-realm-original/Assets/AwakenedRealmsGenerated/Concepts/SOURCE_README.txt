Awakened Realms visual foundation, GPU batch 2026-10-05

Source GPU: tnr-0, NVIDIA RTX A6000
Generation model: local SDXL base
Target orientation: landscape 16:9, matching the original Awakened Realms GDD.
Purpose: production-candidate backgrounds and environment art. These are not automatically final until in-engine review.

Curated candidates:
- splash_v1_2.png: primary splash environment candidate
- login_v1_2.png: primary daytime login candidate
- login_night_v2_2.png: alternate login candidate
- lobby_v1_2.png: formal sanctuary lobby candidate
- lobby_day_v2_1.png: open-air daytime lobby candidate
- lobby_night_v2_1.png: nighttime lobby candidate
- summon_v1_2.png: summon chamber candidate
- campaign_v1_2.png: campaign overview candidate
- battle_v1_2.png: generic battle environment candidate
- arena_v2_2.png: PvP arena candidate
- boss_fire_v2_2.png: fire boss arena
- boss_forest_v2_1.png: forest boss arena
- boss_ice_v2_2.png: ice boss arena
- boss_void_v2_2.png: void boss arena
- guild_v2_1.png: guild hall candidate
- coop_v2_1.png: co-op environment candidate
- hero_roster_v2_1.png: hero roster backdrop candidate
- inventory_v2_2.png: inventory backdrop candidate
- leaderboard_v2_1.png: leaderboard backdrop candidate
- loading_v2_2.png: loading backdrop candidate
- mail_v2_2.png: mail backdrop candidate
- shop_v2_2.png: shop backdrop candidate
- tower_v2_1.png: tower mode candidate

Selection policy:
- Original Awakened Realms assets remain authoritative where stronger.
- Generated backgrounds fill missing or weak environmental presentation.
- No generated hero replacement is approved by this manifest.
- Final use requires Unity composition review, readability review under UI overlays, compression/import tuning, and Samsung device QA.

Second curated GPU pass:
- world/: ten chapter environments plus tutorial, event, guild raid, PvP arena, dragon raid and titan raid backgrounds.
- bosses/: Ember Titan, Worldroot Guardian, Tide Leviathan and Eclipse Sovereign boss concept candidates.
- These remain visual-production candidates pending in-engine composition, animation treatment, collision/readability review, and device QA.

Faction VFX pass:
- vfx/: curated basic, skill, and ultimate effect concepts for Ember, Tide, Verdant, Radiant, and Umbral factions.
- bosses/boss_fallen_seraph_2.png: Radiant Fallen Seraph boss concept candidate, completing the five-faction first boss concept set.

Progression VFX pass:
- progression/: curated star-up effects for Rare, Epic, Legendary, and Mythic, duplicate conversion, fodder fusion, summon reveals by rarity, level-up, power-up, gear enhancement, skill unlock, chapter clear, and idle reward claim.
- These are source concepts for in-engine VFX composition. Final runtime effects should be rebuilt as performant layered sprites/particles rather than shipped as static square cards where inappropriate.

Equipment and enemy concept pass:
- equipment/: curated five-slot equipment concept set for Ember, Tide, Verdant, Radiant, and Umbral. These are inventory-art candidates and style references, not final stat data.
- enemies/: curated three-enemy first-pass roster per faction, 15 total. These are combat-art candidates intended for later cutout/animation conversion and runtime readability review.

UI icon pass:
- ui-icons/: curated first-pass icons for currencies, summon tickets, energy, XP, ascension, guild/arena/raid currencies, quest/achievement/daily, mail, tower, boss, shop, inventory, friends, and settings.
- Final UI adoption requires readability checks at actual mobile icon sizes and alignment with the existing original UI kit.

Evolution aura pass:
- evolution-auras/: curated faction aura concepts for 8-star, 11-star, 13-star, and 15-star evolution treatments across Ember, Tide, Verdant, Radiant, and Umbral.
- Use only milestones applicable to the hero rarity. Legendary major visual evolution remains 8-star and 11-star. Mythic major visual evolution remains 8-star, 11-star, and 13-star, with 15-star reserved for apex completion treatment rather than a separate required redesign unless design review approves it.
