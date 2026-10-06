#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using AwakenedRealm.MetaSystems;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Deterministic validation suite for the AwakenedRealm.MetaSystems domain:
/// reward bundles, quests, achievements, daily login, mail, tower, bosses,
/// shop/economy, and live-event foundations. All time inputs are supplied
/// explicitly; no wall-clock reads occur anywhere.
/// </summary>
public static class ValidateMetaSystems
{
    [MenuItem("Awakened Realms/Validate Meta Systems")]
    public static void Run()
    {
        // ---- Reward bundle: nonnegative validation + atomic merge ----
        bool negativeRejected = false;
        try { var bad = new MetaRewardBundle(-1, 0, 0, 0); }
        catch (ArgumentOutOfRangeException) { negativeRejected = true; }
        Assert(negativeRejected, "Negative currency rejected");

        bool negativeItemRejected = false;
        try
        {
            var bad = new MetaRewardBundle(0, 0, 0, 0,
                new Dictionary<string, long> { { "item-ore", -5 } });
        }
        catch (ArgumentOutOfRangeException) { negativeItemRejected = true; }
        Assert(negativeItemRejected, "Negative item quantity rejected");

        var a = new MetaRewardBundle(10, 5, 1, 20,
            new Dictionary<string, long> { { "item-ore", 3 } });
        var b = new MetaRewardBundle(5, 0, 0, 10,
            new Dictionary<string, long> { { "item-ore", 2 }, { "item-gem", 1 } });
        MetaRewardBundle merged = a.Merge(b);
        Assert(merged.Gold == 15 && merged.Gems == 5 && merged.SummonTickets == 1 && merged.PlayerXp == 30,
            "Merge sums currency fields");
        Assert(merged.ItemQuantity("item-ore") == 5 && merged.ItemQuantity("item-gem") == 1,
            "Merge sums item quantities");
        Assert(a.ItemQuantity("item-gem") == 0 && a.Gold == 10, "Merge does not mutate operands");

        // ---- Quest log: duplicate ID rejection, complete/claim once, resets ----
        var defs = new List<MetaQuestDefinition>
        {
            new MetaQuestDefinition("daily-clear-3", MetaQuestCategory.Daily,
                MetaQuestObjectiveType.ClearStages, "", 3, new MetaRewardBundle(100, 0, 0, 50)),
            new MetaQuestDefinition("daily-win-5", MetaQuestCategory.Daily,
                MetaQuestObjectiveType.WinBattles, "", 5, new MetaRewardBundle(150, 0, 0, 75)),
            new MetaQuestDefinition("weekly-summon-10", MetaQuestCategory.Weekly,
                MetaQuestObjectiveType.SummonHeroes, "", 10, new MetaRewardBundle(0, 100, 0, 0)),
            new MetaQuestDefinition("prog-starup-1", MetaQuestCategory.Progression,
                MetaQuestObjectiveType.StarUpHero, "", 1, new MetaRewardBundle(0, 0, 1, 0)),
        };
        var quests = new MetaQuestLog(defs);

        bool dupQuestRejected = false;
        try
        {
            var dup = new MetaQuestLog(new[]
            {
                defs[0],
                new MetaQuestDefinition("daily-clear-3", MetaQuestCategory.Daily,
                    MetaQuestObjectiveType.WinBattles, "", 2, MetaRewardBundle.Empty)
            });
        }
        catch (InvalidOperationException) { dupQuestRejected = true; }
        Assert(dupQuestRejected, "Duplicate quest ID rejected");

        MetaRewardBundle reward;
        Assert(!quests.TryClaim("daily-clear-3", out reward), "Incomplete quest claim fails");
        quests.AddProgress("daily-clear-3", 2);
        Assert(!quests.StateFor("daily-clear-3").Completed, "Below target not complete");
        quests.AddProgress("daily-clear-3", 5);
        MetaQuestProgress state = quests.StateFor("daily-clear-3");
        Assert(state.Completed && state.Progress == 3, "Progress clamps to target and completes");
        Assert(quests.TryClaim("daily-clear-3", out reward) && reward.Gold == 100, "Completed quest claims");
        Assert(!quests.TryClaim("daily-clear-3", out reward), "Quest claim is once-only");

        // Daily reset on a new key clears daily progress but not weekly/progression.
        Assert(quests.ResetDaily("2026-10-05"), "First daily reset applies");
        Assert(!quests.ResetDaily("2026-10-05"), "Same-day key does not re-reset");
        MetaQuestProgress dailyAfter = quests.StateFor("daily-clear-3");
        Assert(!dailyAfter.Completed && !dailyAfter.Claimed && dailyAfter.Progress == 0,
            "Daily quest state resets");
        quests.AddProgress("prog-starup-1", 1);
        Assert(quests.StateFor("prog-starup-1").Completed, "Progression quest unaffected by daily reset");
        Assert(quests.ResetDaily("2026-10-06"), "Next-day key resets again");

        Assert(quests.ResetWeekly("2026-W41"), "First weekly reset applies");
        Assert(!quests.ResetWeekly("2026-W41"), "Same-week key does not re-reset");
        Assert(quests.ResetWeekly("2026-W42"), "Next-week key resets");

        // ---- Achievements: complete + claim once, permanent ----
        var ach = new MetaAchievementLog(new[]
        {
            new MetaAchievementDefinition("ach-boss-10", MetaQuestObjectiveType.DefeatBoss, "", 10,
                new MetaRewardBundle(0, 200, 0, 0))
        });

        bool dupAchRejected = false;
        try
        {
            var dup = new MetaAchievementLog(new[]
            {
                new MetaAchievementDefinition("ach-boss-10", MetaQuestObjectiveType.DefeatBoss, "", 5, MetaRewardBundle.Empty),
                new MetaAchievementDefinition("ach-boss-10", MetaQuestObjectiveType.WinBattles, "", 5, MetaRewardBundle.Empty)
            });
        }
        catch (InvalidOperationException) { dupAchRejected = true; }
        Assert(dupAchRejected, "Duplicate achievement ID rejected");

        MetaRewardBundle achReward;
        Assert(!ach.TryClaim("ach-boss-10", out achReward), "Incomplete achievement claim fails");
        ach.AddProgress("ach-boss-10", 9);
        Assert(!ach.StateFor("ach-boss-10").Completed, "Below threshold not complete");
        ach.AddProgress("ach-boss-10", 1);
        Assert(ach.StateFor("ach-boss-10").Completed, "Threshold completes achievement");
        Assert(ach.TryClaim("ach-boss-10", out achReward) && achReward.Gems == 200,
            "Completed achievement claims");
        Assert(!ach.TryClaim("ach-boss-10", out achReward), "Achievement claim is once-only");

        // ---- Daily login: same-day rejection, deterministic day advance ----
        var calendar = new MetaDailyLoginCalendar(new[]
        {
            new MetaRewardBundle(100, 0, 0, 0), new MetaRewardBundle(200, 0, 0, 0),
            new MetaRewardBundle(300, 0, 0, 0), new MetaRewardBundle(400, 0, 0, 0),
            new MetaRewardBundle(500, 0, 0, 0), new MetaRewardBundle(600, 0, 0, 0),
            new MetaRewardBundle(700, 50, 1, 0),
        });
        var login = new MetaDailyLoginState();
        MetaRewardBundle loginReward;
        Assert(login.TryClaim(calendar, "2026-10-05", out loginReward) && loginReward.Gold == 100,
            "Day-1 login claims first slot");
        Assert(!login.TryClaim(calendar, "2026-10-05", out loginReward), "Same day cannot claim twice");
        Assert(login.NextCycleDay == 2, "Next claim advances the cycle");
        // A missed day does not corrupt state: skipping 10-06 lands on slot 2 anyway.
        Assert(login.TryClaim(calendar, "2026-10-07", out loginReward) && loginReward.Gold == 200,
            "Skipped day still yields next deterministic slot");
        for (int d = 8; d <= 12; d++)
            Assert(login.TryClaim(calendar, "2026-10-" + d.ToString("D2"), out loginReward), "Cycle advances");
        Assert(login.NextCycleDay == 1, "Cycle wraps to day 1 after 7 claims");

        // ---- Mail: expiry, claim once, deterministic prune ----
        var mailbox = new MetaMailbox();
        const long nowTicks = 638000000000000000L;
        mailbox.Deliver(new MetaMailMessage("mail-1", "mail.welcome.t", "mail.welcome.b",
            new MetaRewardBundle(500, 10, 0, 0), nowTicks + TimeSpan.TicksPerDay));
        mailbox.Deliver(new MetaMailMessage("mail-2", "mail.expired.t", "mail.expired.b",
            new MetaRewardBundle(1, 0, 0, 0), nowTicks - 1));
        mailbox.Deliver(new MetaMailMessage("mail-3", "mail.gone.t", "mail.gone.b",
            MetaRewardBundle.Empty, nowTicks + TimeSpan.TicksPerDay));

        bool dupMailRejected = false;
        try
        {
            mailbox.Deliver(new MetaMailMessage("mail-1", "t", "b", MetaRewardBundle.Empty, 0));
        }
        catch (InvalidOperationException) { dupMailRejected = true; }
        Assert(dupMailRejected, "Duplicate mail ID rejected");

        MetaRewardBundle mailReward;
        Assert(mailbox.TryClaim("mail-1", nowTicks, out mailReward) && mailReward.Gold == 500,
            "Unexpired mail claims");
        Assert(!mailbox.TryClaim("mail-1", nowTicks, out mailReward), "Mail claim is once-only");
        Assert(!mailbox.TryClaim("mail-2", nowTicks, out mailReward), "Expired mail rejects claim");
        mailbox.Delete("mail-3");
        Assert(!mailbox.TryClaim("mail-3", nowTicks, out mailReward), "Deleted mail rejects claim");
        Assert(mailbox.Prune(nowTicks) == 2, "Prune removes expired + deleted deterministically");
        Assert(mailbox.Mail.Count == 1 && mailbox.Mail[0].MailId == "mail-1",
            "Prune preserves surviving mail order");

        // ---- Tower: no-skip, boss every 10, first-clear rewards ----
        Assert(MetaTowerCatalog.FloorCount == 100, "Tower has 100 floors");
        for (int floor = 10; floor <= 100; floor += 10)
            Assert(MetaTowerCatalog.IsBossFloor(floor), "Every 10th floor is a boss floor");
        Assert(!MetaTowerCatalog.IsBossFloor(9) && !MetaTowerCatalog.IsBossFloor(11),
            "Non-10th floors are not boss floors");

        var tower = new MetaTowerProgress();
        MetaRewardBundle floorReward;
        Assert(!tower.TryClearFloor(2, out floorReward), "Cannot skip to floor 2");
        Assert(tower.TryClearFloor(1, out floorReward) && floorReward.Gold == 100,
            "Floor 1 first-clear reward");
        Assert(tower.HighestClearedFloor == 1 && tower.NextFloor == 2, "Next floor is monotonic");
        Assert(!tower.TryClearFloor(1, out floorReward), "Re-clearing an old floor fails");
        Assert(!tower.TryClearFloor(5, out floorReward), "Skipping ahead fails");
        for (int f = 2; f <= 9; f++)
            Assert(tower.TryClearFloor(f, out floorReward), "Sequential floors clear");
        Assert(tower.TryClearFloor(10, out floorReward) && floorReward.SummonTickets == 1,
            "Boss floor 10 pays boss-tier reward");

        // ---- Bosses: 10 chapter bosses + repeatable world boss ----
        MetaBossDefinition[] bosses = MetaBossCatalog.Bosses;
        Assert(bosses.Length == CampaignBossCount() + 1, "10 chapter bosses + world boss");
        for (int chapter = 1; chapter <= 10; chapter++)
        {
            MetaBossDefinition boss = MetaBossCatalog.BossForChapter(chapter);
            Assert(boss.Chapter == chapter && !boss.Repeatable, "Campaign boss chapter wiring");
            Assert(boss.RewardTiers.Length == 3 && boss.RewardTiers[0].Gold > boss.RewardTiers[1].Gold,
                "Chapter boss reward tiers descend");
            Assert(boss.RecommendedPower == 5000L * chapter, "Recommended power scales by chapter");
        }
        Assert(MetaBossCatalog.WorldBoss.Repeatable && MetaBossCatalog.WorldBoss.Chapter == 0,
            "World boss is repeatable and non-campaign");
        Assert(MetaBossCatalog.WorldBoss.RewardTiers.Length == 3, "World boss has reward tiers");

        // ---- Shop: atomic purchase, limits, reset keys ----
        var shop = new MetaShopState(new[]
        {
            new MetaShopItem("shop-ticket-1", MetaCurrencyType.Gems, 100, 3, 5,
                new MetaRewardBundle(0, 0, 1, 0)),
            new MetaShopItem("shop-gold-pack", MetaCurrencyType.Gems, 50, 0, 0,
                new MetaRewardBundle(1000, 0, 0, 0)),
        });

        bool dupShopRejected = false;
        try
        {
            var dup = new MetaShopState(new[]
            {
                new MetaShopItem("shop-dup", MetaCurrencyType.Gold, 1, 0, 0, MetaRewardBundle.Empty),
                new MetaShopItem("shop-dup", MetaCurrencyType.Gold, 2, 0, 0, MetaRewardBundle.Empty)
            });
        }
        catch (InvalidOperationException) { dupShopRejected = true; }
        Assert(dupShopRejected, "Duplicate shop item ID rejected");

        var wallet = new MetaWallet { Gems = 250 };
        var inventory = new Dictionary<string, long>(StringComparer.Ordinal);
        MetaRewardBundle bought;
        // Insufficient funds: buy 2 (200 gems), third costs 100 but only 50 left -> atomic fail.
        Assert(shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought), "Purchase 1");
        Assert(shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought), "Purchase 2");
        Assert(wallet.Gems == 50 && wallet.SummonTickets == 2, "Debits accumulate correctly");
        long gemsBefore = wallet.Gems;
        Assert(!shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought),
            "Insufficient currency rejects purchase");
        Assert(wallet.Gems == gemsBefore && shop.DailyPurchases("shop-ticket-1") == 2,
            "Failed purchase mutates nothing (atomic)");

        wallet.Gems = 1000;
        Assert(shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought), "Purchase 3 hits daily limit");
        Assert(!shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought),
            "Daily limit blocks further purchases");
        Assert(shop.DailyPurchases("shop-ticket-1") == 3, "Daily counter reflects purchases");

        Assert(shop.ResetDaily("2026-10-06"), "Shop daily reset applies on new key");
        Assert(shop.DailyPurchases("shop-ticket-1") == 0, "Daily counters cleared");
        Assert(shop.WeeklyPurchases("shop-ticket-1") == 3, "Weekly counters persist across day reset");
        Assert(shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought), "Purchase 4");
        Assert(shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought), "Purchase 5");
        Assert(!shop.TryPurchase("shop-ticket-1", wallet, inventory, out bought),
            "Weekly limit blocks purchase 6");
        Assert(shop.ResetWeekly("2026-W42"), "Shop weekly reset applies on new key");
        Assert(shop.WeeklyPurchases("shop-ticket-1") == 0, "Weekly counters cleared");

        // ---- Events: window activity + duplicate/window validation ----
        const long startTicks = 638000000000000000L;
        const long endTicks = startTicks + TimeSpan.TicksPerDay;
        var liveEvent = new MetaEventDefinition(
            "event-double-gold", startTicks, endTicks, true,
            new Dictionary<string, int> { { "gold_gain_bp", 20000 } },
            new[] { "reward-table-event-1" });
        Assert(liveEvent.IsActive(startTicks), "Active at start tick");
        Assert(liveEvent.IsActive(endTicks - 1), "Active before end");
        Assert(!liveEvent.IsActive(endTicks), "Inactive at end (exclusive)");
        Assert(!liveEvent.IsActive(startTicks - 1), "Inactive before start");
        var disabled = new MetaEventDefinition(
            "event-off", startTicks, endTicks, false, null, null);
        Assert(!disabled.IsActive(startTicks), "Disabled event never active");
        Assert(liveEvent.ModifierBp("gold_gain_bp") == 20000, "Modifier basis points read");
        Assert(liveEvent.RewardTableKeys.Count == 1 && liveEvent.RewardTableKeys[0] == "reward-table-event-1",
            "Reward table keys preserved");

        bool badWindowRejected = false;
        try
        {
            var bad = new MetaEventDefinition("event-bad", endTicks, startTicks, true, null, null);
        }
        catch (ArgumentException) { badWindowRejected = true; }
        Assert(badWindowRejected, "Invalid window (end <= start) rejected");

        var catalog = new MetaEventCatalog(new[] { liveEvent, disabled });
        Assert(catalog.ActiveAt(startTicks + 1).Count == 1, "Catalog filters to active events");
        Assert(catalog.CombinedModifierBp("gold_gain_bp", startTicks + 1) == 20000,
            "Combined modifier reflects active event only");

        bool dupEventRejected = false;
        try
        {
            var dup = new MetaEventCatalog(new[]
            {
                liveEvent,
                new MetaEventDefinition("event-double-gold", startTicks, endTicks, true, null, null)
            });
        }
        catch (InvalidOperationException) { dupEventRejected = true; }
        Assert(dupEventRejected, "Duplicate event ID rejected");

        Debug.Log("AWAKENED_REALMS_META_SYSTEMS_PASS");
    }

    static int CampaignBossCount()
    {
        return AwakenedRealm.Progression.CampaignCatalog.ChapterCount;
    }

    static void Assert(bool condition, string label)
    {
        if (!condition)
            throw new InvalidOperationException("MetaSystems validation failed: " + label);
    }
}
#endif
