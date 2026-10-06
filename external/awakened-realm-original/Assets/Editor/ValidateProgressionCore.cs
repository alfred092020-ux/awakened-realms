#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Text;
using AwakenedRealm.Enums;
using AwakenedRealm.Persistence;
using AwakenedRealm.Progression;
using UnityEditor;
using UnityEngine;

public static class ValidateProgressionCore
{
    [MenuItem("Awakened Realms/Validate Progression Core")]
    public static void Run()
    {
        // --- Star progression -------------------------------------------------
        Assert(StarProgressionRules.StartingStars(HeroRarity.rare) == 3, "Rare start");
        Assert(StarProgressionRules.MaxStars(HeroRarity.rare) == 5, "Rare cap");
        Assert(StarProgressionRules.StartingStars(HeroRarity.epic) == 4, "Epic start");
        Assert(StarProgressionRules.MaxStars(HeroRarity.epic) == 8, "Epic cap");
        Assert(StarProgressionRules.StartingStars(HeroRarity.legendary) == 5, "Legendary start");
        Assert(StarProgressionRules.MaxStars(HeroRarity.legendary) == 11, "Legendary cap");
        Assert(StarProgressionRules.StartingStars(HeroRarity.mythic) == 6, "Mythic start");
        Assert(StarProgressionRules.MaxStars(HeroRarity.mythic) == 15, "Mythic cap");

        Assert(StarProgressionRules.IsMajorEvolutionMilestone(HeroRarity.legendary, 8), "Legendary 8 evolution");
        Assert(StarProgressionRules.IsMajorEvolutionMilestone(HeroRarity.legendary, 11), "Legendary 11 evolution");
        Assert(StarProgressionRules.IsMajorEvolutionMilestone(HeroRarity.mythic, 8), "Mythic 8 evolution");
        Assert(StarProgressionRules.IsMajorEvolutionMilestone(HeroRarity.mythic, 11), "Mythic 11 evolution");
        Assert(StarProgressionRules.IsMajorEvolutionMilestone(HeroRarity.mythic, 13), "Mythic 13 evolution");
        Assert(!StarProgressionRules.IsMajorEvolutionMilestone(HeroRarity.mythic, 15), "Mythic 15 is apex, not major redesign");
        Assert(StarProgressionRules.IsApexCompletion(HeroRarity.mythic, 15), "Mythic 15 apex");

        var hero = new OwnedHeroProgression("hero-test", HeroRarity.legendary);
        StarUpRequirement requirement = StarProgressionRules.NextRequirement(hero.Rarity, hero.Stars);
        hero.DuplicateCopies = requirement.DuplicateCopies - 1;
        hero.Fodder = requirement.Fodder;
        int copiesBefore = hero.DuplicateCopies;
        int fodderBefore = hero.Fodder;
        int starsBefore = hero.Stars;
        Assert(!hero.TryStarUp(), "Insufficient copies reject");
        Assert(hero.DuplicateCopies == copiesBefore && hero.Fodder == fodderBefore && hero.Stars == starsBefore, "Failed star-up is atomic");

        hero.DuplicateCopies = requirement.DuplicateCopies;
        Assert(hero.TryStarUp(), "Sufficient resources star up");
        Assert(hero.Stars == starsBefore + 1, "Exactly one star gained");
        Assert(hero.DuplicateCopies == 0 && hero.Fodder == 0, "Exact resources consumed");

        // --- Hero-only save round-trip + legacy migration ---------------------
        var original = new List<OwnedHeroProgression>
        {
            new OwnedHeroProgression("hero-a", HeroRarity.rare, 7) { DuplicateCopies = 3, Fodder = 9 },
            new OwnedHeroProgression("hero-b", HeroRarity.mythic, 11) { Stars = 13, DuplicateCopies = 2, Fodder = 50 }
        };
        string json = ProgressionSave.Serialize(original);
        List<OwnedHeroProgression> loaded = ProgressionSave.Deserialize(
            json,
            new HashSet<string>(new[] { "hero-a", "hero-b" }, StringComparer.Ordinal));
        Assert(loaded.Count == 2, "Round-trip hero count");
        Assert(loaded[1].Stars == 13 && loaded[1].Level == 11, "Round-trip state");

        string legacyJson = "{\"Version\":1,\"Heroes\":[{\"HeroId\":\"hero-a\",\"Rarity\":1,\"Level\":5}]}";
        List<OwnedHeroProgression> migrated = ProgressionSave.Deserialize(
            legacyJson,
            new HashSet<string>(new[] { "hero-a" }, StringComparer.Ordinal));
        Assert(migrated[0].Stars == 3, "Legacy save migrates to rarity start");
        Assert(migrated[0].DuplicateCopies == 0 && migrated[0].Fodder == 0, "Legacy resources default zero");

        Assert(ThrowsInvalidOperation(() => ProgressionSave.Deserialize(
            "{\"Version\":2,\"Heroes\":[{\"HeroId\":\"hero-a\",\"Rarity\":1,\"Level\":1,\"Stars\":3},{\"HeroId\":\"hero-a\",\"Rarity\":1,\"Level\":1,\"Stars\":3}]}",
            new HashSet<string>(new[] { "hero-a" }, StringComparer.Ordinal))),
            "Duplicate hero records rejected");

        // --- Summon configuration + pool validation ---------------------------
        var config = new SummonConfig();
        config.Validate();
        Assert(config.RareWeight + config.EpicWeight + config.LegendaryWeight + config.MythicWeight
            == SummonConfig.WeightScale, "Summon weights sum to 1,000,000");

        SummonHeroPool pool = BuildTestPool();
        Assert(ThrowsInvalidOperation(() => new SummonHeroPool(new[]
            {
                new SummonPoolEntry("dupe", HeroRarity.rare),
                new SummonPoolEntry("dupe", HeroRarity.rare)
            })), "Duplicate pool ID rejected");

        // --- Summon execution --------------------------------------------------
        var state = NewSummonableState();
        var pull = SummonExecutor.SummonSingle(state, pool, new XorShift64Random(111), config).Pulls[0];
        Assert(pull.IsNew, "First unlock is new");
        OwnedHeroProgression unlocked = state.FindHero(pull.HeroId);
        Assert(unlocked != null && unlocked.Stars == StarProgressionRules.StartingStars(unlocked.Rarity),
            "First unlock starts at rarity starting stars");

        // Single-legendary pool + hard pity one step away forces a pull on an
        // already-owned hero, so the duplicate increment is deterministic.
        SummonHeroPool singleLegendary = new SummonHeroPool(new[]
            {
                new SummonPoolEntry("rare-x", HeroRarity.rare),
                new SummonPoolEntry("epic-x", HeroRarity.epic),
                new SummonPoolEntry("leg-x", HeroRarity.legendary),
                new SummonPoolEntry("mythic-x", HeroRarity.mythic)
            });
        var seeded = new GameProgressionState
        {
            SummonTickets = 4,
            LegendaryPity = SummoningService.LegendaryHardPity - 1
        };
        seeded.Heroes.Add(new OwnedHeroProgression("leg-x", HeroRarity.legendary));
        int heroCountBefore = seeded.Heroes.Count;
        SummonPullResult dup = SummonExecutor
            .SummonSingle(seeded, singleLegendary, new XorShift64Random(500), config).Pulls[0];
        Assert(dup.HeroId == "leg-x" && !dup.IsNew && dup.ResultingDuplicateCopies == 1,
            "Duplicate increments exactly once");
        Assert(seeded.Heroes.Count == heroCountBefore,
            "Duplicate does not create roster entry");

        var tenPullState = NewSummonableState();
        SummonResult tenPull = SummonExecutor.SummonTenPull(tenPullState, pool,
            new XorShift64Random(9), config);
        Assert(tenPull.Pulls.Count == 10, "10-pull produces exactly 10");
        Assert(tenPull.ContainsEpicOrBetter, "10-pull contains Epic-or-better");
        Assert(tenPull.SpentWith == SummonSpendKind.tickets && tenPull.SpentAmount == 10,
            "10-pull spends whole ticket request");

        var gemState = new GameProgressionState { SummonTickets = 3, Gems = 3000 };
        int ticketsBeforeGem = gemState.SummonTickets;
        SummonResult gemPull = SummonExecutor.SummonTenPull(gemState, pool,
            new XorShift64Random(10), config);
        Assert(gemPull.SpentWith == SummonSpendKind.gems && gemPull.SpentAmount == 2700,
            "Gems fund request tickets cannot cover");
        Assert(gemState.SummonTickets == ticketsBeforeGem, "Spend never mixes currencies");

        var broke = new GameProgressionState { SummonTickets = 0, Gems = 50 };
        string brokeSnapshot = Snapshot(broke);
        Assert(ThrowsInvalidOperation(() =>
            SummonExecutor.SummonSingle(broke, pool, new XorShift64Random(1), config)),
            "Insufficient resources rejected");
        Assert(Snapshot(broke) == brokeSnapshot,
            "Failed summon leaves roster, pity and wallet unchanged");

        var legendaryPity = NewSummonableState();
        legendaryPity.LegendaryPity = SummoningService.LegendaryHardPity - 1;
        legendaryPity.MythicPity = 25;
        SummonPullResult forcedLegendary = SummonExecutor
            .SummonSingle(legendaryPity, pool, new XorShift64Random(7), config).Pulls[0];
        Assert(forcedLegendary.Rarity == HeroRarity.legendary && forcedLegendary.PityForced,
            "Hard Legendary pity forces Legendary");
        Assert(legendaryPity.LegendaryPity == 0 && legendaryPity.MythicPity == 26,
            "Legendary pity resets only its own track");

        var mythicPity = NewSummonableState();
        mythicPity.MythicPity = SummoningService.MythicHardPity - 1;
        mythicPity.LegendaryPity = SummoningService.LegendaryHardPity - 1;
        SummonPullResult forcedMythic = SummonExecutor
            .SummonSingle(mythicPity, pool, new XorShift64Random(8), config).Pulls[0];
        Assert(forcedMythic.Rarity == HeroRarity.mythic && forcedMythic.PityForced,
            "Hard Mythic pity forces Mythic");
        Assert(mythicPity.MythicPity == 0 && mythicPity.LegendaryPity == 0,
            "Mythic pity resets both tracks");

        var seedA = NewSummonableState();
        var seedB = NewSummonableState();
        SummonResult runA = SummonExecutor.SummonTenPull(seedA, pool, new XorShift64Random(42), config);
        SummonResult runB = SummonExecutor.SummonTenPull(seedB, pool, new XorShift64Random(42), config);
        Assert(PullsSignature(runA) == PullsSignature(runB),
            "Same seed and state produce identical pulls");

        // --- Campaign catalog --------------------------------------------------
        CampaignStage[] stages = CampaignCatalog.Stages;
        Assert(stages.Length == CampaignCatalog.ChapterCount * CampaignCatalog.StagesPerChapter,
            "10 chapters x 12 stages");
        var stageIds = new HashSet<int>();
        for (int chapter = 1; chapter <= CampaignCatalog.ChapterCount; chapter++)
        {
            int normal = 0, elite = 0, boss = 0;
            for (int index = 1; index <= CampaignCatalog.StagesPerChapter; index++)
            {
                CampaignStage stage = CampaignCatalog.GetStage(CampaignCatalog.MakeStageId(chapter, index));
                Assert(stage.Chapter == chapter && stage.IndexInChapter == index, "Stage coordinates match ID");
                Assert(stageIds.Add(stage.StageId), "Stage IDs unique");
                if (stage.Type == CampaignStageType.Normal) normal++;
                else if (stage.Type == CampaignStageType.Elite) elite++;
                else boss++;
            }
            Assert(normal == 10 && elite == 1 && boss == 1, "Chapter is 10 Normal + 1 Elite + 1 Boss");
        }
        Assert(CampaignCatalog.NextStageAfter(0).StageId == CampaignCatalog.MinStage,
            "Zero progress points at first stage");
        Assert(CampaignCatalog.NextStageAfter(CampaignCatalog.MakeStageId(1, 12)).StageId
            == CampaignCatalog.MakeStageId(2, 1), "NextStageAfter crosses chapter boundary");
        Assert(CampaignCatalog.NextStageAfter(CampaignCatalog.MaxStage) == null,
            "Campaign ends after final Boss");
        Assert(ThrowsInvalidOperation(() =>
            new GameProgressionState { HighestClearedStage = 555 }.Validate()),
            "Invalid HighestClearedStage rejected");

        // --- Idle rewards -------------------------------------------------------
        var idleConfig = new IdleRewardConfig();
        idleConfig.Validate();
        var t0 = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);

        var fresh = new GameProgressionState();
        IdleReward firstClaim = IdleRewards.Claim(fresh, t0, idleConfig);
        Assert(firstClaim.Gold == 0 && firstClaim.PlayerXp == 0,
            "First claim grants zero offline reward");
        Assert(fresh.LastSeenUtcTicks == t0.Ticks, "First claim establishes timestamp");

        var capped = new GameProgressionState { HighestClearedStage = CampaignCatalog.MakeStageId(3, 6) };
        capped.LastSeenUtc = t0;
        IdleReward cappedPreview = IdleRewards.Preview(capped, t0.AddHours(30), idleConfig);
        Assert(cappedPreview.Capped && cappedPreview.MinutesCounted == 12 * 60,
            "Idle preview caps at 12 hours");
        string cappedSnapshot = Snapshot(capped) + "|" + capped.LastSeenUtcTicks;
        IdleRewards.Preview(capped, t0.AddHours(30), idleConfig);
        Assert(Snapshot(capped) + "|" + capped.LastSeenUtcTicks == cappedSnapshot,
            "Idle preview does not mutate");

        var claimer = new GameProgressionState { HighestClearedStage = CampaignCatalog.MakeStageId(3, 6) };
        claimer.LastSeenUtc = t0;
        IdleReward earned = IdleRewards.Claim(claimer, t0.AddHours(2), idleConfig);
        Assert(earned.Gold > 0 && earned.PlayerXp > 0, "Idle claim grants rewards");
        Assert(claimer.Gold == earned.Gold && claimer.PlayerXp == earned.PlayerXp,
            "Claim applies rewards atomically");
        Assert(claimer.LastSeenUtcTicks == t0.AddHours(2).Ticks,
            "Claim stamps nowUtc exactly once");

        long lastSeen = claimer.LastSeenUtcTicks;
        IdleReward backwards = IdleRewards.Claim(claimer, t0.AddHours(1), idleConfig);
        Assert(backwards.Gold == 0 && backwards.PlayerXp == 0, "Backwards clock grants zero");
        Assert(claimer.LastSeenUtcTicks == lastSeen, "LastSeenUtc never moves backwards");
        IdleReward sameInstant = IdleRewards.Claim(claimer, t0.AddHours(2), idleConfig);
        Assert(sameInstant.Gold == 0 && sameInstant.PlayerXp == 0, "Repeat claim grants zero");

        var onboarding = new GameProgressionState();
        onboarding.LastSeenUtc = t0;
        IdleReward baseline = IdleRewards.Preview(onboarding, t0.AddMinutes(60), idleConfig);
        var progressed = new GameProgressionState { HighestClearedStage = CampaignCatalog.MaxStage };
        progressed.LastSeenUtc = t0;
        IdleReward late = IdleRewards.Preview(progressed, t0.AddMinutes(60), idleConfig);
        Assert(baseline.Gold > 0 && baseline.PlayerXp > 0, "Stage 0 keeps onboarding baseline");
        Assert(late.Gold > baseline.Gold && late.PlayerXp > baseline.PlayerXp,
            "Idle rate scales monotonically with progress");

        // --- Full state save round-trip -----------------------------------------
        var metaState = new GameProgressionState
        {
            Gold = 12345,
            Gems = 678,
            SummonTickets = 9,
            PlayerXp = 4321,
            HighestClearedStage = CampaignCatalog.MakeStageId(4, 7),
            LegendaryPity = 12,
            MythicPity = 34,
            LastSeenUtcTicks = t0.AddHours(5).Ticks
        };
        metaState.Heroes.Add(new OwnedHeroProgression("hero-a", HeroRarity.epic, 20)
        {
            Stars = 6,
            DuplicateCopies = 2,
            Fodder = 7
        });
        metaState.Validate();

        string stateJson = ProgressionSave.SerializeState(metaState);
        GameProgressionState restored = ProgressionSave.DeserializeState(
            stateJson,
            new HashSet<string>(new[] { "hero-a" }, StringComparer.Ordinal));
        Assert(Snapshot(metaState) == Snapshot(restored), "v3 state round-trip");
        Assert(restored.Heroes.Count == 1 && restored.Heroes[0].Stars == 6,
            "v3 hero record round-trip");

        GameProgressionState legacyState = ProgressionSave.DeserializeState(legacyJson,
            new HashSet<string>(new[] { "hero-a" }, StringComparer.Ordinal));
        Assert(legacyState.Gold == 0 && legacyState.Gems == 0 && legacyState.SummonTickets == 0
            && legacyState.PlayerXp == 0 && legacyState.HighestClearedStage == 0
            && legacyState.LastSeenUtcTicks == 0,
            "Older payload defaults metagame fields to zero, invents no currency");
        Assert(legacyState.Heroes.Count == 1 && legacyState.Heroes[0].Stars == 3,
            "Legacy v1 hero migration still passes");

        Assert(ThrowsInvalidOperation(() => ProgressionSave.DeserializeState(
            "{\"Version\":3,\"Heroes\":[{\"HeroId\":\"hero-a\",\"Rarity\":1,\"Level\":1,\"Stars\":3},{\"HeroId\":\"hero-a\",\"Rarity\":1,\"Level\":1,\"Stars\":3}]}",
            new HashSet<string>(new[] { "hero-a" }, StringComparer.Ordinal))),
            "v3 duplicate hero record rejected");
        Assert(ThrowsInvalidOperation(() => ProgressionSave.DeserializeState(
            "{\"Version\":3,\"Heroes\":[],\"Gold\":-5}")),
            "v3 negative resources rejected");
        Assert(ThrowsInvalidOperation(() => ProgressionSave.DeserializeState(
            "{\"Version\":3,\"Heroes\":[],\"HighestClearedStage\":555}")),
            "v3 invalid campaign stage rejected");
        Assert(ThrowsInvalidOperation(() => ProgressionSave.DeserializeState(
            "{\"Version\":3,\"Heroes\":[],\"MythicPity\":120}")),
            "v3 pity out of range rejected");
        Assert(ThrowsInvalidOperation(() => ProgressionSave.DeserializeState(
            "{\"Version\":3,\"Heroes\":[],\"LastSeenUtcTicks\":\"not-a-number\"}")),
            "v3 invalid timestamp rejected");
        Assert(ThrowsInvalidOperation(() => ProgressionSave.DeserializeState(
            "{\"Version\":3,\"Heroes\":[{\"HeroId\":\"hero-a\",\"Rarity\":1,\"Level\":1,\"Stars\":9}]}",
            new HashSet<string>(new[] { "hero-a" }, StringComparer.Ordinal))),
            "v3 hero star range enforced");
        Assert(ThrowsInvalidOperation(() => ProgressionSave.DeserializeState("{\"Version\":99,\"Heroes\":[]}")),
            "Future save version rejected");

        Debug.Log("AWAKENED_REALMS_PROGRESSION_CORE_PASS");
    }

    static void Assert(bool condition, string label)
    {
        if (!condition)
            throw new InvalidOperationException("Progression validation failed: " + label);
    }

    static bool ThrowsInvalidOperation(Action action)
    {
        try
        {
            action();
            return false;
        }
        catch (InvalidOperationException)
        {
            return true;
        }
    }

    static GameProgressionState NewSummonableState()
    {
        return new GameProgressionState { SummonTickets = 100, Gems = 100000 };
    }

    static SummonHeroPool BuildTestPool()
    {
        var entries = new List<SummonPoolEntry>();
        for (int i = 1; i <= 6; i++)
            entries.Add(new SummonPoolEntry("rare-" + i, HeroRarity.rare));
        for (int i = 1; i <= 4; i++)
            entries.Add(new SummonPoolEntry("epic-" + i, HeroRarity.epic));
        for (int i = 1; i <= 2; i++)
            entries.Add(new SummonPoolEntry("legendary-" + i, HeroRarity.legendary));
        entries.Add(new SummonPoolEntry("mythic-1", HeroRarity.mythic));
        return new SummonHeroPool(entries);
    }

    static string PullsSignature(SummonResult result)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < result.Pulls.Count; i++)
        {
            SummonPullResult pull = result.Pulls[i];
            sb.Append(pull.HeroId).Append(':').Append(pull.Rarity)
              .Append(':').Append(pull.IsNew ? 1 : 0)
              .Append(':').Append(pull.ResultingDuplicateCopies)
              .Append(':').Append(pull.PityForced ? 1 : 0)
              .Append(';');
        }
        return sb.ToString();
    }

    static string Snapshot(GameProgressionState state)
    {
        var sb = new StringBuilder();
        sb.Append("G").Append(state.Gold)
          .Append("|E").Append(state.Gems)
          .Append("|T").Append(state.SummonTickets)
          .Append("|X").Append(state.PlayerXp)
          .Append("|L").Append(state.LegendaryPity)
          .Append("|M").Append(state.MythicPity)
          .Append("|S").Append(state.HighestClearedStage)
          .Append("|H").Append(state.Heroes.Count);
        for (int i = 0; i < state.Heroes.Count; i++)
        {
            OwnedHeroProgression hero = state.Heroes[i];
            sb.Append('|').Append(hero.HeroId).Append(',')
              .Append((int)hero.Rarity).Append(',')
              .Append(hero.Level).Append(',')
              .Append(hero.Stars).Append(',')
              .Append(hero.DuplicateCopies).Append(',')
              .Append(hero.Fodder);
        }
        return sb.ToString();
    }
}
#endif
