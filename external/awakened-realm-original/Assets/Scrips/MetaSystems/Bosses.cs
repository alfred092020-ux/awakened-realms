using System;
using System.Collections.Generic;
using AwakenedRealm.Progression;

namespace AwakenedRealm.MetaSystems
{
    /// <summary>
    /// Immutable boss encounter definition. IDs are stable strings of the form
    /// "boss-chapter-N" for campaign bosses and "boss-world" for the repeatable
    /// world-boss encounter. Reward tiers are ordered lists of bundles; the
    /// caller resolves which tier applies (e.g. by damage bracket or kill rank).
    /// Story text is intentionally absent: this is pure mechanics data.
    /// </summary>
    public sealed class MetaBossDefinition
    {
        public readonly string BossId;
        public readonly int Chapter;
        public readonly long RecommendedPower;
        public readonly bool Repeatable;
        public readonly MetaRewardBundle[] RewardTiers;

        /// <param name="chapter">Campaign chapter (1..10), or 0 for non-campaign bosses.</param>
        /// <param name="rewardTiers">Ordered reward tiers, best first; must be nonempty.</param>
        public MetaBossDefinition(
            string bossId,
            int chapter,
            long recommendedPower,
            bool repeatable,
            MetaRewardBundle[] rewardTiers)
        {
            if (string.IsNullOrEmpty(bossId))
                throw new ArgumentException("Boss ID must be a nonempty stable string.", nameof(bossId));
            if (chapter < 0)
                throw new ArgumentOutOfRangeException(nameof(chapter), "Chapter must be 0 (non-campaign) or a positive chapter number.");
            if (recommendedPower < 0)
                throw new ArgumentOutOfRangeException(nameof(recommendedPower), "Recommended power must be nonnegative.");
            if (rewardTiers == null || rewardTiers.Length == 0)
                throw new ArgumentException("Bosses need at least one reward tier.", nameof(rewardTiers));
            for (int i = 0; i < rewardTiers.Length; i++)
            {
                if (rewardTiers[i] == null)
                    throw new ArgumentException("Reward tiers must not contain nulls.", nameof(rewardTiers));
            }

            BossId = bossId;
            Chapter = chapter;
            RecommendedPower = recommendedPower;
            Repeatable = repeatable;
            RewardTiers = (MetaRewardBundle[])rewardTiers.Clone();
        }
    }

    /// <summary>
    /// Deterministic boss catalog: one campaign boss per chapter 1..10 (aligned
    /// with <see cref="CampaignCatalog.ChapterCount"/>) plus a single repeatable
    /// world-boss definition. Reward tiers scale with chapter depth.
    /// </summary>
    public static class MetaBossCatalog
    {
        public const string WorldBossId = "boss-world";

        static readonly MetaBossDefinition[] OrderedBosses;
        static readonly Dictionary<string, MetaBossDefinition> ById;

        static MetaBossCatalog()
        {
            int chapters = CampaignCatalog.ChapterCount;
            var bosses = new List<MetaBossDefinition>(chapters + 1);

            for (int chapter = 1; chapter <= chapters; chapter++)
            {
                // Deterministic per-chapter tiers: full clear, partial, attempt.
                var tiers = new[]
                {
                    new MetaRewardBundle(2000L * chapter, 100L * chapter, 1, 1000L * chapter),
                    new MetaRewardBundle(1000L * chapter, 50L * chapter, 0, 500L * chapter),
                    new MetaRewardBundle(250L * chapter, 10L * chapter, 0, 125L * chapter),
                };
                bosses.Add(new MetaBossDefinition(
                    "boss-chapter-" + chapter,
                    chapter,
                    5000L * chapter,
                    repeatable: false,
                    rewardTiers: tiers));
            }

            // Repeatable world boss: damage-bracket tiers, deterministic.
            var worldTiers = new[]
            {
                new MetaRewardBundle(50000, 500, 3, 25000),
                new MetaRewardBundle(20000, 200, 1, 10000),
                new MetaRewardBundle(5000, 50, 0, 2500),
            };
            bosses.Add(new MetaBossDefinition(
                WorldBossId,
                chapter: 0,
                recommendedPower: 75000,
                repeatable: true,
                rewardTiers: worldTiers));

            OrderedBosses = bosses.ToArray();
            ById = new Dictionary<string, MetaBossDefinition>(OrderedBosses.Length, StringComparer.Ordinal);
            for (int i = 0; i < OrderedBosses.Length; i++)
                ById.Add(OrderedBosses[i].BossId, OrderedBosses[i]);
        }

        /// <summary>All boss definitions in catalog order (campaign 1..10, then world boss).</summary>
        public static MetaBossDefinition[] Bosses
        {
            get { return (MetaBossDefinition[])OrderedBosses.Clone(); }
        }

        public static bool IsBoss(string bossId)
        {
            return bossId != null && ById.ContainsKey(bossId);
        }

        public static MetaBossDefinition GetBoss(string bossId)
        {
            MetaBossDefinition boss;
            if (bossId == null || !ById.TryGetValue(bossId, out boss))
                throw new ArgumentOutOfRangeException(nameof(bossId), bossId, "Unknown boss ID.");
            return boss;
        }

        /// <summary>Campaign boss for a chapter (1..10).</summary>
        public static MetaBossDefinition BossForChapter(int chapter)
        {
            if (chapter < 1 || chapter > CampaignCatalog.ChapterCount)
                throw new ArgumentOutOfRangeException(nameof(chapter), chapter, "Unknown campaign chapter.");
            return GetBoss("boss-chapter-" + chapter);
        }

        public static MetaBossDefinition WorldBoss
        {
            get { return GetBoss(WorldBossId); }
        }
    }
}
