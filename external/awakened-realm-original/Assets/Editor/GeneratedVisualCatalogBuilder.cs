using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using AwakenedRealm.Presentation;
using UnityEditor;
using UnityEngine;

namespace AwakenedRealm.EditorTools
{
    /// <summary>
    /// Finds the curated source art by filename, applies generated import settings, and
    /// writes/updates the ScriptableObject catalogs under
    /// Assets/Resources/AwakenedRealmsGenerated. Fails closed (throws) if a required
    /// source file is missing or ambiguous so we never write a half-populated catalog.
    /// </summary>
    public static class GeneratedVisualCatalogBuilder
    {
        const string ConceptsRoot = "Assets/AwakenedRealmsGenerated/Concepts";
        const string OutputFolder = "Assets/Resources/AwakenedRealmsGenerated";
        const string CatalogAssetPath = OutputFolder + "/VisualCatalog.asset";
        const string EffectCatalogAssetPath = OutputFolder + "/EffectCatalog.asset";
        const string TimingAssetPath = OutputFolder + "/TimingConfig.asset";

        [MenuItem("Awakened Realms/Generated Art/Build Visual Catalog")]
        public static void BuildFromMenu()
        {
            var report = Build();
            Debug.Log(report);
        }

        /// <summary>Applies imports and writes all catalog assets. Returns a summary.</summary>
        public static string Build()
        {
            var failures = new List<string>();

            // ---- Resolve every required source path up-front (fail closed). ----
            var required = BuildRequiredSourceMap();
            var resolved = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var kv in required)
            {
                var key = kv.Key;
                var fileName = kv.Value;
                var path = FindUniqueSourcePath(fileName);
                if (path == null)
                {
                    failures.Add($"missing required source '{fileName}' for key '{key}'");
                    continue;
                }
                resolved[key] = path;
            }

            if (failures.Count > 0)
            {
                throw new InvalidOperationException("Visual catalog source resolution failed: " + string.Join(" | ", failures));
            }

            // ---- Reimport everything under the concepts root so the importer rules stick. ----
            var allSources = Directory.GetFiles(ConceptsRoot, "*.png", SearchOption.AllDirectories);
            foreach (var path in allSources)
            {
                AssetDatabase.ImportAsset(ToUnityPath(path), ImportAssetOptions.ForceUpdate);
            }

            // ---- Build catalog entries. ----
            var entries = new List<GeneratedVisualCatalog.Entry>();
            foreach (var kv in resolved)
            {
                var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(kv.Value);
                if (sprite == null)
                {
                    failures.Add($"resolved path '{kv.Value}' did not load as Sprite for key '{kv.Key}'");
                    continue;
                }
                entries.Add(new GeneratedVisualCatalog.Entry
                {
                    key = kv.Key,
                    kind = KindFor(kv.Key),
                    sprite = sprite,
                    sourceAssetPath = kv.Value,
                    isConceptReferenceOnly = IsConceptReferenceOnly(kv.Value),
                });
            }

            // Add optional (non-required) concept/source art that resolved fine.
            foreach (var extra in BuildOptionalEntries())
            {
                if (!entries.Any(e => e.key == extra.key))
                {
                    entries.Add(extra);
                }
            }

            if (failures.Count > 0)
            {
                throw new InvalidOperationException("Visual catalog sprite load failed: " + string.Join(" | ", failures));
            }

            var effects = BuildEffectEntries(failures);
            if (failures.Count > 0)
            {
                throw new InvalidOperationException("Effect catalog build failed: " + string.Join(" | ", failures));
            }

            // ---- Write/update the ScriptableObject assets. ----
            EnsureFolder(OutputFolder);
            var catalog = LoadOrCreate<GeneratedVisualCatalog>(CatalogAssetPath);
            catalog.ReplaceEntries(entries.OrderBy(e => e.key, StringComparer.Ordinal));
            EditorUtility.SetDirty(catalog);

            var effectCatalog = LoadOrCreate<GeneratedEffectCatalog>(EffectCatalogAssetPath);
            effectCatalog.ReplaceEffects(effects.OrderBy(e => e.effectId, StringComparer.Ordinal));
            EditorUtility.SetDirty(effectCatalog);

            var timing = LoadOrCreate<PresentationTimingConfig>(TimingAssetPath);
            EditorUtility.SetDirty(timing);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            return $"Visual catalog built: {entries.Count} visual entries, {effects.Count} effect descriptors -> {CatalogAssetPath}";
        }

        // ---- Required source map --------------------------------------------------

        /// <summary>key -> exact curated filename under Concepts/.</summary>
        static Dictionary<string, string> BuildRequiredSourceMap()
        {
            var map = new Dictionary<string, string>(StringComparer.Ordinal)
            {
                // Core screens
                { GeneratedVisualKeys.Splash, "backgrounds/splash_v1_2.png" },
                { GeneratedVisualKeys.Login, "backgrounds/login_v1_2.png" },
                { GeneratedVisualKeys.LobbyDay, "backgrounds/lobby_day_v2_1.png" },
                { GeneratedVisualKeys.LobbyNight, "backgrounds/lobby_night_v2_1.png" },
                { GeneratedVisualKeys.Campaign, "backgrounds/campaign_v1_2.png" },
                { GeneratedVisualKeys.Summon, "backgrounds/summon_v1_2.png" },
                { GeneratedVisualKeys.Battle, "backgrounds/battle_v1_2.png" },
                { GeneratedVisualKeys.Arena, "backgrounds/arena_v2_2.png" },
                { GeneratedVisualKeys.Tower, "backgrounds/tower_v2_1.png" },
                { GeneratedVisualKeys.Shop, "backgrounds/shop_v2_2.png" },
                { GeneratedVisualKeys.Mail, "backgrounds/mail_v2_2.png" },
                { GeneratedVisualKeys.Inventory, "backgrounds/inventory_v2_2.png" },
                { GeneratedVisualKeys.Roster, "backgrounds/hero_roster_v2_1.png" },
                { GeneratedVisualKeys.Guild, "backgrounds/guild_v2_1.png" },
                { GeneratedVisualKeys.Coop, "backgrounds/coop_v2_1.png" },
                { GeneratedVisualKeys.Loading, "backgrounds/loading_v2_2.png" },

                // Chapters 1..10
                { GeneratedVisualKeys.Chapter(1), "world/chapter01_dawnreach_2.png" },
                { GeneratedVisualKeys.Chapter(2), "world/chapter02_verdant_2.png" },
                { GeneratedVisualKeys.Chapter(3), "world/chapter03_ember_2.png" },
                { GeneratedVisualKeys.Chapter(4), "world/chapter04_tide_2.png" },
                { GeneratedVisualKeys.Chapter(5), "world/chapter05_frost_2.png" },
                { GeneratedVisualKeys.Chapter(6), "world/chapter06_umbral_2.png" },
                { GeneratedVisualKeys.Chapter(7), "world/chapter07_desert_1.png" },
                { GeneratedVisualKeys.Chapter(8), "world/chapter08_crystal_2.png" },
                { GeneratedVisualKeys.Chapter(9), "world/chapter09_celestial_2.png" },
                { GeneratedVisualKeys.Chapter(10), "world/chapter10_rift_2.png" },

                // Bosses
                { GeneratedVisualKeys.BossEmberTitan, "bosses/ember_titan_3.png" },
                { GeneratedVisualKeys.BossTideLeviathan, "bosses/tide_leviathan_1.png" },
                { GeneratedVisualKeys.BossWorldrootGuardian, "bosses/worldroot_guardian_2.png" },
                { GeneratedVisualKeys.BossFallenSeraph, "bosses/boss_fallen_seraph_2.png" },
                { GeneratedVisualKeys.BossEclipseSovereign, "bosses/eclipse_sovereign_3.png" },

                // Rarity frames
                { GeneratedVisualKeys.RarityFrame(AwakenedRealm.Enums.HeroRarity.rare), "meta-ui/frame_rare_1.png" },
                { GeneratedVisualKeys.RarityFrame(AwakenedRealm.Enums.HeroRarity.epic), "meta-ui/frame_epic_1.png" },
                { GeneratedVisualKeys.RarityFrame(AwakenedRealm.Enums.HeroRarity.legendary), "meta-ui/frame_legendary_2.png" },
                { GeneratedVisualKeys.RarityFrame(AwakenedRealm.Enums.HeroRarity.mythic), "meta-ui/frame_mythic_2.png" },

                // Role icons
                { GeneratedVisualKeys.RoleAttacker, "meta-ui/role_attacker_2.png" },
                { GeneratedVisualKeys.RoleDefender, "meta-ui/role_defender_1.png" },
                { GeneratedVisualKeys.RoleSupport, "meta-ui/role_support_1.png" },

                // Campaign node icons
                { GeneratedVisualKeys.NodeNormal, "meta-ui/node_normal_1.png" },
                { GeneratedVisualKeys.NodeElite, "meta-ui/node_elite_2.png" },
                { GeneratedVisualKeys.NodeBoss, "meta-ui/node_boss_1.png" },
                { GeneratedVisualKeys.NodeLocked, "meta-ui/node_locked_2.png" },

                // Currencies / tickets / keys
                { GeneratedVisualKeys.IconGold, "ui-icons/gold_2.png" },
                { GeneratedVisualKeys.IconGems, "ui-icons/gems_1.png" },
                { GeneratedVisualKeys.IconEnergy, "ui-icons/energy_1.png" },
                { GeneratedVisualKeys.IconHeroXp, "ui-icons/hero_xp_1.png" },
                { GeneratedVisualKeys.IconBasicTicket, "ui-icons/basic_ticket_2.png" },
                { GeneratedVisualKeys.IconAdvancedTicket, "ui-icons/advanced_ticket_1.png" },
                { GeneratedVisualKeys.IconArenaToken, "ui-icons/arena_token_2.png" },
                { GeneratedVisualKeys.IconRaidToken, "ui-icons/raid_token_1.png" },
                { GeneratedVisualKeys.IconGuildCoin, "ui-icons/guild_coin_2.png" },

                // Progression / ceremony
                { GeneratedVisualKeys.CeremonyLevelUp, "progression/levelup_2.png" },
                { GeneratedVisualKeys.CeremonyPowerUp, "progression/powerup_2.png" },
                { GeneratedVisualKeys.CeremonyChapterClear, "progression/chapter_clear_2.png" },
                { GeneratedVisualKeys.CeremonySkillUnlock, "progression/skill_unlock_2.png" },
                { GeneratedVisualKeys.CeremonyGearUpgrade, "progression/gear_upgrade_2.png" },
                { GeneratedVisualKeys.CeremonyIdleClaim, "progression/idle_claim_2.png" },
                { GeneratedVisualKeys.CeremonyDuplicateConvert, "progression/duplicate_convert_2.png" },
                { GeneratedVisualKeys.CeremonyFodderMerge, "progression/fodder_merge_2.png" },

                // Summon portals per rarity
                { GeneratedVisualKeys.SummonPortal(AwakenedRealm.Enums.HeroRarity.rare), "meta-ui/summon_portal_rare_1.png" },
                { GeneratedVisualKeys.SummonPortal(AwakenedRealm.Enums.HeroRarity.epic), "meta-ui/summon_portal_epic_1.png" },
                { GeneratedVisualKeys.SummonPortal(AwakenedRealm.Enums.HeroRarity.legendary), "meta-ui/summon_portal_legendary_1.png" },
                { GeneratedVisualKeys.SummonPortal(AwakenedRealm.Enums.HeroRarity.mythic), "meta-ui/summon_portal_mythic_1.png" },

                // Summon reveal art per rarity
                { GeneratedVisualKeys.SummonReveal(AwakenedRealm.Enums.HeroRarity.rare), "progression/summon_rare_2.png" },
                { GeneratedVisualKeys.SummonReveal(AwakenedRealm.Enums.HeroRarity.epic), "progression/summon_epic_2.png" },
                { GeneratedVisualKeys.SummonReveal(AwakenedRealm.Enums.HeroRarity.legendary), "progression/summon_legendary_2.png" },
                { GeneratedVisualKeys.SummonReveal(AwakenedRealm.Enums.HeroRarity.mythic), "progression/summon_mythic_2.png" },

                // Star-up ceremony per rarity
                { GeneratedVisualKeys.StarUpCeremony(AwakenedRealm.Enums.HeroRarity.rare), "progression/rare_starup_2.png" },
                { GeneratedVisualKeys.StarUpCeremony(AwakenedRealm.Enums.HeroRarity.epic), "progression/epic_starup_2.png" },
                { GeneratedVisualKeys.StarUpCeremony(AwakenedRealm.Enums.HeroRarity.legendary), "progression/legendary_starup_2.png" },
                { GeneratedVisualKeys.StarUpCeremony(AwakenedRealm.Enums.HeroRarity.mythic), "progression/mythic_starup_2.png" },
            };

            // Evolution auras per faction/tier
            foreach (var faction in GeneratedVisualKeys.FactionIds)
            {
                foreach (var tier in GeneratedVisualKeys.EvolutionTiers)
                {
                    map[GeneratedVisualKeys.EvolutionAura(faction, tier)] =
                        $"evolution-auras/{faction}_evo{tier}_2.png";
                }
            }

            return map;
        }

        /// <summary>Optional catalog entries that are not strictly required but useful.</summary>
        static List<GeneratedVisualCatalog.Entry> BuildOptionalEntries()
        {
            var list = new List<GeneratedVisualCatalog.Entry>();
            void TryAdd(string key, string fileName, GeneratedVisualKind kind)
            {
                var path = FindUniqueSourcePath(fileName);
                if (path == null)
                {
                    return;
                }
                var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(path);
                if (sprite == null)
                {
                    return;
                }
                list.Add(new GeneratedVisualCatalog.Entry
                {
                    key = key,
                    kind = kind,
                    sprite = sprite,
                    sourceAssetPath = path,
                    isConceptReferenceOnly = IsConceptReferenceOnly(path),
                });
            }

            TryAdd("screen.login.night", "backgrounds/login_night_v2_2.png", GeneratedVisualKind.ScreenBackground);
            TryAdd("screen.lobby.alt", "backgrounds/lobby_v1_2.png", GeneratedVisualKind.ScreenBackground);
            TryAdd("screen.leaderboard", "backgrounds/leaderboard_v2_1.png", GeneratedVisualKind.ScreenBackground);
            TryAdd("world.event.festival", "world/event_festival_2.png", GeneratedVisualKind.ChapterBackground);
            TryAdd("world.guild_raid_hall", "world/guild_raid_hall_1.png", GeneratedVisualKind.ChapterBackground);
            TryAdd("world.pvp_arena", "world/pvp_arena_2.png", GeneratedVisualKind.ChapterBackground);
            TryAdd("world.raid_dragon", "world/raid_dragon_1.png", GeneratedVisualKind.ChapterBackground);
            TryAdd("world.raid_titan", "world/raid_titan_1.png", GeneratedVisualKind.ChapterBackground);
            TryAdd("world.tutorial", "world/tutorial_1.png", GeneratedVisualKind.ChapterBackground);

            // Enemies
            foreach (var file in Directory.GetFiles(ConceptsRoot + "/enemies", "*.png"))
            {
                var name = Path.GetFileNameWithoutExtension(file);
                TryAdd($"enemy.{name}", $"enemies/{name}.png", GeneratedVisualKind.EnemyPortrait);
            }

            // Equipment
            foreach (var file in Directory.GetFiles(ConceptsRoot + "/equipment", "*.png"))
            {
                var name = Path.GetFileNameWithoutExtension(file);
                TryAdd($"equipment.{name}", $"equipment/{name}.png", GeneratedVisualKind.EquipmentIcon);
            }

            // Meta-ui utility icons not already required
            TryAdd("icon.achievement", "ui-icons/achievement_1.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.ascension", "ui-icons/ascension_2.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.boss", "ui-icons/boss_2.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.daily", "ui-icons/daily_2.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.friends", "ui-icons/friends_2.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.inventory", "ui-icons/inventory_2.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.mail", "ui-icons/mail_1.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.quest", "ui-icons/quest_2.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.settings", "ui-icons/settings_2.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.shop", "ui-icons/shop_1.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("icon.tower", "ui-icons/tower_1.png", GeneratedVisualKind.CurrencyIcon);

            TryAdd("badge.achievement", "meta-ui/badge_achievement_1.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("badge.daily", "meta-ui/badge_daily_1.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("badge.event", "meta-ui/badge_event_1.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("badge.quest", "meta-ui/badge_quest_1.png", GeneratedVisualKind.CurrencyIcon);
            TryAdd("meta.power_rating", "meta-ui/power_rating_2.png", GeneratedVisualKind.CurrencyIcon);

            return list;
        }

        // ---- Effect catalog ---------------------------------------------------------

        static List<GeneratedEffectCatalog.EffectEntry> BuildEffectEntries(List<string> failures)
        {
            var list = new List<GeneratedEffectCatalog.EffectEntry>();

            void Add(string effectId, string faction, string fileName)
            {
                var path = FindUniqueSourcePath(fileName);
                if (path == null)
                {
                    failures.Add($"missing concept FX source '{fileName}' for effect '{effectId}'");
                    return;
                }
                var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(path);
                if (sprite == null)
                {
                    failures.Add($"concept FX '{fileName}' failed to load as Sprite");
                    return;
                }
                list.Add(new GeneratedEffectCatalog.EffectEntry
                {
                    effectId = effectId,
                    faction = faction ?? string.Empty,
                    sourceSprite = sprite,
                    sourceAssetPath = path,
                    requiresRuntimeRebuild = true,
                });
            }

            // Faction VFX concepts (variant suffix differs per file; resolve by prefix)
            foreach (var faction in GeneratedVisualKeys.FactionIds)
            {
                AddGlob($"vfx.{faction}.basic", faction, "vfx", $"{faction}_basic_");
                AddGlob($"vfx.{faction}.skill", faction, "vfx", $"{faction}_skill_");
                AddGlob($"vfx.{faction}.ultimate", faction, "vfx", $"{faction}_ultimate_");
            }

            // Combat FX concepts (semantic IDs)
            Add("combat.blind", "", "combat-fx/blind_2.png");
            Add("combat.boss_break", "", "combat-fx/boss_break_1.png");
            Add("combat.boss_enrage", "", "combat-fx/boss_enrage_2.png");
            Add("combat.buff", "", "combat-fx/buff_2.png");
            Add("combat.burn", "", "combat-fx/burn_1.png");
            Add("combat.crit", "", "combat-fx/crit_2.png");
            Add("combat.debuff", "", "combat-fx/debuff_1.png");
            Add("combat.heal", "", "combat-fx/heal_1.png");
            Add("combat.poison", "", "combat-fx/poison_1.png");
            Add("combat.shield", "", "combat-fx/shield_2.png");
            Add("combat.silence", "", "combat-fx/silence_1.png");
            Add("combat.stun", "", "combat-fx/stun_1.png");
            Add("combat.ultimate_charge", "", "combat-fx/ultimate_charge_1.png");
            Add("combat.ultimate_impact", "", "combat-fx/ultimate_impact_2.png");
            Add("combat.victory", "", "combat-fx/victory_1.png");

            foreach (var faction in GeneratedVisualKeys.FactionIds)
            {
                AddGlob($"combat.{faction}.cast", faction, "combat-fx", $"{faction}_cast_");
                AddGlob($"combat.{faction}.hit", faction, "combat-fx", $"{faction}_hit_");
                AddGlob($"combat.{faction}.trail", faction, "combat-fx", $"{faction}_trail_");
            }

            return list;

            void AddGlob(string effectId, string faction, string folder, string filePrefix)
            {
                var dir = ConceptsRoot + "/" + folder;
                var matches = Directory.Exists(dir)
                    ? Directory.GetFiles(dir, filePrefix + "*.png")
                    : Array.Empty<string>();
                if (matches.Length != 1)
                {
                    failures.Add($"concept FX '{folder}/{filePrefix}*' resolved {matches.Length} files (need exactly 1) for effect '{effectId}'");
                    return;
                }
                Add(effectId, faction, folder + "/" + Path.GetFileName(matches[0]));
            }
        }

        // ---- Helpers ------------------------------------------------------------------

        static bool IsConceptReferenceOnly(string assetPath)
        {
            var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            var data = importer != null ? importer.userData : null;
            return !string.IsNullOrEmpty(data) && data.Contains("requires-runtime-rebuild");
        }

        static GeneratedVisualKind KindFor(string key)
        {
            if (key.StartsWith("chapter.", StringComparison.Ordinal)) return GeneratedVisualKind.ChapterBackground;
            if (key.StartsWith("boss.", StringComparison.Ordinal)) return GeneratedVisualKind.BossPortrait;
            if (key.StartsWith("enemy.", StringComparison.Ordinal)) return GeneratedVisualKind.EnemyPortrait;
            if (key.StartsWith("equipment.", StringComparison.Ordinal)) return GeneratedVisualKind.EquipmentIcon;
            if (key.StartsWith("rarity.frame.", StringComparison.Ordinal)) return GeneratedVisualKind.RarityFrame;
            if (key.StartsWith("role.", StringComparison.Ordinal)) return GeneratedVisualKind.RoleIcon;
            if (key.StartsWith("campaign.node.", StringComparison.Ordinal)) return GeneratedVisualKind.CampaignNodeIcon;
            if (key.StartsWith("icon.", StringComparison.Ordinal) || key.StartsWith("badge.", StringComparison.Ordinal)) return GeneratedVisualKind.CurrencyIcon;
            if (key.StartsWith("evolution.aura.", StringComparison.Ordinal)) return GeneratedVisualKind.EvolutionAura;
            if (key.StartsWith("ceremony.", StringComparison.Ordinal) || key.StartsWith("starup.", StringComparison.Ordinal) || key.StartsWith("summon.reveal.", StringComparison.Ordinal)) return GeneratedVisualKind.ProgressionCeremony;
            if (key.StartsWith("summon.portal.", StringComparison.Ordinal)) return GeneratedVisualKind.SummonPortal;
            return GeneratedVisualKind.ScreenBackground;
        }

        /// <summary>Find one file under Concepts by relative path (e.g. "world/foo.png").</summary>
        static string FindUniqueSourcePath(string relativePath)
        {
            var direct = ConceptsRoot + "/" + relativePath;
            if (File.Exists(direct))
            {
                return direct;
            }

            // Fallback: basename lookup across the tree so we fail closed on ambiguity.
            var name = Path.GetFileName(relativePath);
            var matches = Directory.GetFiles(ConceptsRoot, name, SearchOption.AllDirectories)
                .Where(p => Path.GetFileName(p) == name)
                .ToArray();
            if (matches.Length == 1)
            {
                return ToUnityPath(matches[0]);
            }
            return null;
        }

        static string ToUnityPath(string path) => path.Replace('\\', '/');

        static void EnsureFolder(string folderPath)
        {
            if (AssetDatabase.IsValidFolder(folderPath))
            {
                return;
            }
            var parent = Path.GetDirectoryName(folderPath).Replace('\\', '/');
            var leaf = Path.GetFileName(folderPath);
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, leaf);
        }

        static T LoadOrCreate<T>(string path) where T : ScriptableObject
        {
            var existing = AssetDatabase.LoadAssetAtPath<T>(path);
            if (existing != null)
            {
                return existing;
            }
            var created = ScriptableObject.CreateInstance<T>();
            AssetDatabase.CreateAsset(created, path);
            return created;
        }
    }
}
