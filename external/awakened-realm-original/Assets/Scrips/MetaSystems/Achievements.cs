using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    /// <summary>
    /// Immutable permanent achievement definition. Achievements are one-time:
    /// they never reset and their reward can be claimed exactly once.
    /// </summary>
    public sealed class MetaAchievementDefinition
    {
        public readonly string AchievementId;
        public readonly MetaQuestObjectiveType Metric;
        public readonly string MetricKey;
        public readonly long Threshold;
        public readonly MetaRewardBundle Reward;

        public MetaAchievementDefinition(
            string achievementId,
            MetaQuestObjectiveType metric,
            string metricKey,
            long threshold,
            MetaRewardBundle reward)
        {
            if (string.IsNullOrEmpty(achievementId))
                throw new ArgumentException("Achievement ID must be a nonempty stable string.", nameof(achievementId));
            if (threshold <= 0)
                throw new ArgumentOutOfRangeException(nameof(threshold), "Threshold must be positive.");
            if (reward == null)
                throw new ArgumentNullException(nameof(reward));

            AchievementId = achievementId;
            Metric = metric;
            MetricKey = metricKey ?? string.Empty;
            Threshold = threshold;
            Reward = reward;
        }
    }

    /// <summary>
    /// Mutable achievement state. Total progress (clamped to threshold),
    /// completed flag, and the one-time claim flag.
    /// </summary>
    [Serializable]
    public sealed class MetaAchievementState
    {
        public string AchievementId;
        public long TotalProgress;
        public bool Completed;
        public bool Claimed;

        public MetaAchievementState(string achievementId)
        {
            if (string.IsNullOrEmpty(achievementId))
                throw new ArgumentException("Achievement ID must be nonempty.", nameof(achievementId));
            AchievementId = achievementId;
        }

        public bool AddProgress(MetaAchievementDefinition definition, long amount)
        {
            if (definition == null)
                throw new ArgumentNullException(nameof(definition));
            if (definition.AchievementId != AchievementId)
                throw new ArgumentException("Definition/achievement ID mismatch.", nameof(definition));
            if (amount < 0)
                throw new ArgumentOutOfRangeException(nameof(amount), "Progress increments must be nonnegative.");
            if (Claimed)
                return false;

            TotalProgress = Math.Min(definition.Threshold, checked(TotalProgress + amount));
            if (TotalProgress >= definition.Threshold)
                Completed = true;
            return Completed;
        }

        /// <summary>Atomically claims the reward once; fails if incomplete or already claimed.</summary>
        public bool TryClaim(MetaAchievementDefinition definition, out MetaRewardBundle reward)
        {
            if (definition == null)
                throw new ArgumentNullException(nameof(definition));
            if (definition.AchievementId != AchievementId)
                throw new ArgumentException("Definition/achievement ID mismatch.", nameof(definition));

            reward = null;
            if (!Completed || Claimed)
                return false;
            Claimed = true;
            reward = definition.Reward;
            return true;
        }
    }

    /// <summary>
    /// Achievement log: validated catalog plus per-achievement state.
    /// Permanent; no reset API exists by design.
    /// </summary>
    public sealed class MetaAchievementLog
    {
        readonly Dictionary<string, MetaAchievementDefinition> definitions =
            new Dictionary<string, MetaAchievementDefinition>(StringComparer.Ordinal);
        readonly Dictionary<string, MetaAchievementState> states =
            new Dictionary<string, MetaAchievementState>(StringComparer.Ordinal);

        public MetaAchievementLog(IEnumerable<MetaAchievementDefinition> defs)
        {
            if (defs == null)
                throw new ArgumentNullException(nameof(defs));
            foreach (MetaAchievementDefinition def in defs)
            {
                if (def == null)
                    throw new ArgumentException("Achievement catalog must not contain null entries.", nameof(defs));
                if (definitions.ContainsKey(def.AchievementId))
                    throw new InvalidOperationException("Duplicate achievement ID: " + def.AchievementId);
                definitions.Add(def.AchievementId, def);
            }
        }

        public IReadOnlyDictionary<string, MetaAchievementDefinition> Definitions
        {
            get { return definitions; }
        }

        public MetaAchievementState StateFor(string achievementId)
        {
            MetaAchievementState state;
            if (!states.TryGetValue(achievementId, out state))
            {
                if (!definitions.ContainsKey(achievementId))
                    throw new ArgumentOutOfRangeException(nameof(achievementId), achievementId, "Unknown achievement ID.");
                state = new MetaAchievementState(achievementId);
                states.Add(achievementId, state);
            }
            return state;
        }

        public bool AddProgress(string achievementId, long amount)
        {
            MetaAchievementState state = StateFor(achievementId); // throws for unknown IDs
            return state.AddProgress(definitions[achievementId], amount);
        }

        public bool TryClaim(string achievementId, out MetaRewardBundle reward)
        {
            MetaAchievementState state = StateFor(achievementId); // throws for unknown IDs
            return state.TryClaim(definitions[achievementId], out reward);
        }
    }
}
