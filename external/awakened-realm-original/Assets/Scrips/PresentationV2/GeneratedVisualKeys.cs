using AwakenedRealm.Enums;

namespace AwakenedRealm.Presentation
{
    /// <summary>
    /// Stable string keys for every typed slot in GeneratedVisualCatalog. These keys are
    /// written into the catalog asset by the editor builder and must not drift; the
    /// validator fails closed on missing or duplicate keys.
    /// </summary>
    public static class GeneratedVisualKeys
    {
        // ---- Core screens -------------------------------------------------
        public const string Splash = "screen.splash";
        public const string Login = "screen.login";
        public const string LobbyDay = "screen.lobby.day";
        public const string LobbyNight = "screen.lobby.night";
        public const string Campaign = "screen.campaign";
        public const string Summon = "screen.summon";
        public const string Battle = "screen.battle";
        public const string Arena = "screen.arena";
        public const string Tower = "screen.tower";
        public const string Shop = "screen.shop";
        public const string Mail = "screen.mail";
        public const string Inventory = "screen.inventory";
        public const string Roster = "screen.roster";
        public const string Guild = "screen.guild";
        public const string Coop = "screen.coop";
        public const string Loading = "screen.loading";

        public static readonly string[] CoreScreenKeys =
        {
            Splash, Login, LobbyDay, LobbyNight, Campaign, Summon, Battle, Arena,
            Tower, Shop, Mail, Inventory, Roster, Guild, Coop, Loading,
        };

        // ---- Chapter world backgrounds (chapters 1..10) -------------------
        public static string Chapter(int chapter) => $"chapter.{chapter:D2}.background";
        public static readonly string[] ChapterKeys = BuildChapterKeys();

        static string[] BuildChapterKeys()
        {
            var keys = new string[10];
            for (int i = 0; i < keys.Length; i++)
            {
                keys[i] = Chapter(i + 1);
            }
            return keys;
        }

        // ---- Bosses --------------------------------------------------------
        public const string BossEmberTitan = "boss.ember_titan";
        public const string BossTideLeviathan = "boss.tide_leviathan";
        public const string BossWorldrootGuardian = "boss.worldroot_guardian";
        public const string BossFallenSeraph = "boss.fallen_seraph";
        public const string BossEclipseSovereign = "boss.eclipse_sovereign";

        public static readonly string[] BossKeys =
        {
            BossEmberTitan, BossTideLeviathan, BossWorldrootGuardian,
            BossFallenSeraph, BossEclipseSovereign,
        };

        // ---- Rarity frames / portals / ceremony art ------------------------
        public static string RarityFrame(HeroRarity rarity) => $"rarity.frame.{rarity}";
        public static string SummonPortal(HeroRarity rarity) => $"summon.portal.{rarity}";
        public static string SummonReveal(HeroRarity rarity) => $"summon.reveal.{rarity}";
        public static string StarUpCeremony(HeroRarity rarity) => $"starup.ceremony.{rarity}";

        // Rare..mythic are the curated rarities in this batch (common uses rare frame).
        public static readonly HeroRarity[] CuratedRarities =
        {
            HeroRarity.rare, HeroRarity.epic, HeroRarity.legendary, HeroRarity.mythic,
        };

        // ---- Role icons ----------------------------------------------------
        public const string RoleAttacker = "role.attacker";
        public const string RoleDefender = "role.defender";
        public const string RoleSupport = "role.support";

        public static readonly string[] RoleKeys =
        {
            RoleAttacker, RoleDefender, RoleSupport,
        };

        // ---- Campaign node icons --------------------------------------------
        public const string NodeNormal = "campaign.node.normal";
        public const string NodeElite = "campaign.node.elite";
        public const string NodeBoss = "campaign.node.boss";
        public const string NodeLocked = "campaign.node.locked";

        public static readonly string[] NodeKeys =
        {
            NodeNormal, NodeElite, NodeBoss, NodeLocked,
        };

        // ---- Currencies / tickets / utility icons ---------------------------
        public const string IconGold = "icon.gold";
        public const string IconGems = "icon.gems";
        public const string IconEnergy = "icon.energy";
        public const string IconHeroXp = "icon.hero_xp";
        public const string IconBasicTicket = "icon.ticket.basic";
        public const string IconAdvancedTicket = "icon.ticket.advanced";
        public const string IconArenaToken = "icon.arena_token";
        public const string IconRaidToken = "icon.raid_token";
        public const string IconGuildCoin = "icon.guild_coin";

        public static readonly string[] CurrencyKeys =
        {
            IconGold, IconGems, IconEnergy, IconHeroXp, IconBasicTicket,
            IconAdvancedTicket, IconArenaToken, IconRaidToken, IconGuildCoin,
        };

        // ---- Progression / evolution ceremony -------------------------------
        public const string CeremonyLevelUp = "ceremony.levelup";
        public const string CeremonyPowerUp = "ceremony.powerup";
        public const string CeremonyChapterClear = "ceremony.chapter_clear";
        public const string CeremonySkillUnlock = "ceremony.skill_unlock";
        public const string CeremonyGearUpgrade = "ceremony.gear_upgrade";
        public const string CeremonyIdleClaim = "ceremony.idle_claim";
        public const string CeremonyDuplicateConvert = "ceremony.duplicate_convert";
        public const string CeremonyFodderMerge = "ceremony.fodder_merge";

        public static readonly string[] CeremonyKeys =
        {
            CeremonyLevelUp, CeremonyPowerUp, CeremonyChapterClear,
            CeremonySkillUnlock, CeremonyGearUpgrade, CeremonyIdleClaim,
            CeremonyDuplicateConvert, CeremonyFodderMerge,
        };

        // ---- Evolution auras (faction x tier) --------------------------------
        public static readonly string[] FactionIds = { "ember", "radiant", "tide", "umbral", "verdant" };
        public static readonly int[] EvolutionTiers = { 8, 11, 13, 15 };

        public static string EvolutionAura(string faction, int tier) => $"evolution.aura.{faction}.{tier}";
    }
}
