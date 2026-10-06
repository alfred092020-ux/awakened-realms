using AwakenedRealm.Enums;
using UnityEngine;

namespace AwakenedRealm.Presentation
{
    /// <summary>
    /// Runtime accessor for the generated visual catalog. Loads
    /// Assets/Resources/AwakenedRealmsGenerated/VisualCatalog.asset via Resources and
    /// exposes typed getters. All calls are safe: missing catalog, missing key or null
    /// sprite return false / null with a warning rather than throwing. No scene
    /// dependencies.
    /// </summary>
    public static class PresentationVisuals
    {
        static GeneratedVisualCatalog catalog;
        static bool catalogLoadAttempted;
        static GeneratedEffectCatalog effects;
        static bool effectsLoadAttempted;
        static PresentationTimingConfig timing;
        static bool timingLoadAttempted;

        public static GeneratedVisualCatalog Catalog
        {
            get
            {
                EnsureCatalogLoaded();
                return catalog;
            }
        }

        public static GeneratedEffectCatalog Effects
        {
            get
            {
                EnsureEffectsLoaded();
                return effects;
            }
        }

        public static PresentationTimingConfig Timing
        {
            get
            {
                EnsureTimingLoaded();
                return timing;
            }
        }

        static void EnsureCatalogLoaded()
        {
            if (catalogLoadAttempted)
            {
                return;
            }
            catalogLoadAttempted = true;
            catalog = Resources.Load<GeneratedVisualCatalog>(GeneratedVisualCatalog.ResourcePath);
            if (catalog == null)
            {
                Debug.LogWarning($"[PresentationVisuals] Visual catalog missing at Resources/{GeneratedVisualCatalog.ResourcePath}. Run Awakened Realms/Generated Art/Build Visual Catalog.");
            }
        }

        static void EnsureEffectsLoaded()
        {
            if (effectsLoadAttempted)
            {
                return;
            }
            effectsLoadAttempted = true;
            effects = Resources.Load<GeneratedEffectCatalog>(GeneratedEffectCatalog.ResourcePath);
            if (effects == null)
            {
                Debug.LogWarning($"[PresentationVisuals] Effect catalog missing at Resources/{GeneratedEffectCatalog.ResourcePath}. Run Awakened Realms/Generated Art/Build Visual Catalog.");
            }
        }

        static void EnsureTimingLoaded()
        {
            if (timingLoadAttempted)
            {
                return;
            }
            timingLoadAttempted = true;
            timing = Resources.Load<PresentationTimingConfig>(PresentationTimingConfig.ResourcePath);
            if (timing == null)
            {
                Debug.LogWarning($"[PresentationVisuals] Timing config missing at Resources/{PresentationTimingConfig.ResourcePath}. Run Awakened Realms/Generated Art/Build Visual Catalog.");
            }
        }

        public static bool TryGet(string key, out Sprite sprite)
        {
            sprite = null;
            var c = Catalog;
            if (c == null || string.IsNullOrEmpty(key))
            {
                return false;
            }

            if (!c.TryGetSprite(key, out sprite))
            {
                Debug.LogWarning($"[PresentationVisuals] Missing sprite for key '{key}'.");
                return false;
            }
            return true;
        }

        public static Sprite Get(string key)
        {
            return TryGet(key, out var sprite) ? sprite : null;
        }

        // ---- Typed getters ------------------------------------------------

        public static Sprite GetScreen(string screenKey) => Get(screenKey);
        public static Sprite GetSplash() => Get(GeneratedVisualKeys.Splash);
        public static Sprite GetLogin() => Get(GeneratedVisualKeys.Login);
        public static Sprite GetLobbyDay() => Get(GeneratedVisualKeys.LobbyDay);
        public static Sprite GetLobbyNight() => Get(GeneratedVisualKeys.LobbyNight);
        public static Sprite GetCampaign() => Get(GeneratedVisualKeys.Campaign);
        public static Sprite GetSummon() => Get(GeneratedVisualKeys.Summon);
        public static Sprite GetBattle() => Get(GeneratedVisualKeys.Battle);
        public static Sprite GetArena() => Get(GeneratedVisualKeys.Arena);
        public static Sprite GetTower() => Get(GeneratedVisualKeys.Tower);
        public static Sprite GetShop() => Get(GeneratedVisualKeys.Shop);
        public static Sprite GetMail() => Get(GeneratedVisualKeys.Mail);
        public static Sprite GetInventory() => Get(GeneratedVisualKeys.Inventory);
        public static Sprite GetRoster() => Get(GeneratedVisualKeys.Roster);
        public static Sprite GetGuild() => Get(GeneratedVisualKeys.Guild);
        public static Sprite GetCoop() => Get(GeneratedVisualKeys.Coop);
        public static Sprite GetLoading() => Get(GeneratedVisualKeys.Loading);

        public static Sprite GetChapterBackground(int chapter) => Get(GeneratedVisualKeys.Chapter(chapter));
        public static Sprite GetBoss(string bossKey) => Get(bossKey);
        public static Sprite GetRarityFrame(HeroRarity rarity) => Get(GeneratedVisualKeys.RarityFrame(rarity));
        public static Sprite GetSummonPortal(HeroRarity rarity) => Get(GeneratedVisualKeys.SummonPortal(rarity));
        public static Sprite GetSummonReveal(HeroRarity rarity) => Get(GeneratedVisualKeys.SummonReveal(rarity));
        public static Sprite GetStarUpCeremony(HeroRarity rarity) => Get(GeneratedVisualKeys.StarUpCeremony(rarity));
        public static Sprite GetRoleIcon(string roleKey) => Get(roleKey);
        public static Sprite GetCampaignNodeIcon(string nodeKey) => Get(nodeKey);
        public static Sprite GetCurrencyIcon(string iconKey) => Get(iconKey);
        public static Sprite GetCeremony(string ceremonyKey) => Get(ceremonyKey);
        public static Sprite GetEvolutionAura(string faction, int tier) => Get(GeneratedVisualKeys.EvolutionAura(faction, tier));

        // ---- Effect concept lookup ----------------------------------------

        public static bool TryGetEffectConcept(string effectId, out GeneratedEffectCatalog.EffectEntry effect)
        {
            effect = null;
            var c = Effects;
            return c != null && c.TryGetEffect(effectId, out effect);
        }

        /// <summary>Reset caches (editor/tests only).</summary>
        public static void ResetCache()
        {
            catalog = null;
            catalogLoadAttempted = false;
            effects = null;
            effectsLoadAttempted = false;
            timing = null;
            timingLoadAttempted = false;
        }
    }
}
