using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    public enum MetaQuestCategory
    {
        Daily,
        Weekly,
        Progression
    }

    /// <summary>
    /// Objective vocabulary shared by quest and achievement definitions.
    /// </summary>
    public enum MetaQuestObjectiveType
    {
        ClearStages,
        WinBattles,
        SummonHeroes,
        LevelHero,
        StarUpHero,
        DefeatBoss,
        ClearTowerFloor,
        SpendCurrency
    }

    /// <summary>
    /// Immutable quest definition. <see cref="QuestId"/> is a stable string ID
    /// (e.g. "daily-clear-3-stages"). <see cref="ObjectiveKey"/> scopes the
    /// objective (e.g. currency ID for SpendCurrency) and may be empty.
    /// </summary>
    public sealed class MetaQuestDefinition
    {
        public readonly string QuestId;
        public readonly MetaQuestCategory Category;
        public readonly MetaQuestObjectiveType Objective;
        public readonly string ObjectiveKey;
        public readonly long TargetCount;
        public readonly MetaRewardBundle Reward;

        public MetaQuestDefinition(
            string questId,
            MetaQuestCategory category,
            MetaQuestObjectiveType objective,
            string objectiveKey,
            long targetCount,
            MetaRewardBundle reward)
        {
            if (string.IsNullOrEmpty(questId))
                throw new ArgumentException("Quest ID must be a nonempty stable string.", nameof(questId));
            if (targetCount <= 0)
                throw new ArgumentOutOfRangeException(nameof(targetCount), "Target count must be positive.");
            if (reward == null)
                throw new ArgumentNullException(nameof(reward));

            QuestId = questId;
            Category = category;
            Objective = objective;
            ObjectiveKey = objectiveKey ?? string.Empty;
            TargetCount = targetCount;
            Reward = reward;
        }
    }

    /// <summary>
    /// Mutable per-quest progress state. Progress is clamped to the target
    /// count; rewards can be claimed exactly once.
    /// </summary>
    [Serializable]
    public sealed class MetaQuestProgress
    {
        public string QuestId;
        public long Progress;
        public bool Completed;
        public bool Claimed;

        public MetaQuestProgress(string questId)
        {
            if (string.IsNullOrEmpty(questId))
                throw new ArgumentException("Quest ID must be nonempty.", nameof(questId));
            QuestId = questId;
        }

        /// <summary>
        /// Adds <paramref name="amount"/> to progress (must be nonnegative)
        /// and marks the quest completed once the target is met.
        /// </summary>
        public bool AddProgress(MetaQuestDefinition definition, long amount)
        {
            if (definition == null)
                throw new ArgumentNullException(nameof(definition));
            if (definition.QuestId != QuestId)
                throw new ArgumentException("Definition/quest ID mismatch.", nameof(definition));
            if (amount < 0)
                throw new ArgumentOutOfRangeException(nameof(amount), "Progress increments must be nonnegative.");
            if (Claimed)
                return false;

            long next = Math.Min(definition.TargetCount, checked(Progress + amount));
            Progress = next;
            if (Progress >= definition.TargetCount)
                Completed = true;
            return Completed;
        }

        /// <summary>Atomically claims the reward once; fails if incomplete or already claimed.</summary>
        public bool TryClaim(MetaQuestDefinition definition, out MetaRewardBundle reward)
        {
            if (definition == null)
                throw new ArgumentNullException(nameof(definition));
            if (definition.QuestId != QuestId)
                throw new ArgumentException("Definition/quest ID mismatch.", nameof(definition));

            reward = null;
            if (!Completed || Claimed)
                return false;
            Claimed = true;
            reward = definition.Reward;
            return true;
        }
    }

    /// <summary>
    /// Quest log keyed by stable quest ID. Owns a validated definition catalog
    /// and per-quest progress records. Daily/weekly resets are driven by
    /// caller-supplied UTC keys; this type never reads wall-clock time.
    /// </summary>
    public sealed class MetaQuestLog
    {
        readonly Dictionary<string, MetaQuestDefinition> definitions =
            new Dictionary<string, MetaQuestDefinition>(StringComparer.Ordinal);
        readonly Dictionary<string, MetaQuestProgress> progress =
            new Dictionary<string, MetaQuestProgress>(StringComparer.Ordinal);

        // Last reset keys applied per time-based category; empty = never reset.
        string dailyKey = string.Empty;
        string weeklyKey = string.Empty;

        public MetaQuestLog(IEnumerable<MetaQuestDefinition> defs)
        {
            if (defs == null)
                throw new ArgumentNullException(nameof(defs));
            foreach (MetaQuestDefinition def in defs)
            {
                if (def == null)
                    throw new ArgumentException("Quest catalog must not contain null entries.", nameof(defs));
                if (definitions.ContainsKey(def.QuestId))
                    throw new InvalidOperationException("Duplicate quest ID: " + def.QuestId);
                definitions.Add(def.QuestId, def);
            }
        }

        public IReadOnlyDictionary<string, MetaQuestDefinition> Definitions
        {
            get { return definitions; }
        }

        public string DailyResetKey
        {
            get { return dailyKey; }
        }

        public string WeeklyResetKey
        {
            get { return weeklyKey; }
        }

        public MetaQuestProgress StateFor(string questId)
        {
            MetaQuestProgress state;
            if (!progress.TryGetValue(questId, out state))
            {
                if (!definitions.ContainsKey(questId))
                    throw new ArgumentOutOfRangeException(nameof(questId), questId, "Unknown quest ID.");
                state = new MetaQuestProgress(questId);
                progress.Add(questId, state);
            }
            return state;
        }

        /// <summary>Increments progress for a quest by ID.</summary>
        public bool AddProgress(string questId, long amount)
        {
            MetaQuestProgress state = StateFor(questId); // throws for unknown IDs
            return state.AddProgress(definitions[questId], amount);
        }

        /// <summary>Claims the quest reward once; returns false when incomplete or already claimed.</summary>
        public bool TryClaim(string questId, out MetaRewardBundle reward)
        {
            MetaQuestProgress state = StateFor(questId); // throws for unknown IDs
            return state.TryClaim(definitions[questId], out reward);
        }

        /// <summary>
        /// Resets Daily quest progress when <paramref name="utcDayKey"/>
        /// differs from the last applied key. Returns true when a reset ran.
        /// Unstarted quests are simply absent from state.
        /// </summary>
        public bool ResetDaily(string utcDayKey)
        {
            if (string.IsNullOrEmpty(utcDayKey))
                throw new ArgumentException("Day key must be nonempty (e.g. \"2026-10-05\").", nameof(utcDayKey));
            if (string.Equals(dailyKey, utcDayKey, StringComparison.Ordinal))
                return false;
            dailyKey = utcDayKey;
            RemoveCategory(MetaQuestCategory.Daily);
            return true;
        }

        /// <summary>
        /// Resets Weekly quest progress when <paramref name="utcWeekKey"/>
        /// differs from the last applied key (e.g. "2026-W41").
        /// </summary>
        public bool ResetWeekly(string utcWeekKey)
        {
            if (string.IsNullOrEmpty(utcWeekKey))
                throw new ArgumentException("Week key must be nonempty (e.g. \"2026-W41\").", nameof(utcWeekKey));
            if (string.Equals(weeklyKey, utcWeekKey, StringComparison.Ordinal))
                return false;
            weeklyKey = utcWeekKey;
            RemoveCategory(MetaQuestCategory.Weekly);
            return true;
        }

        void RemoveCategory(MetaQuestCategory category)
        {
            var doomed = new List<string>();
            foreach (KeyValuePair<string, MetaQuestProgress> pair in progress)
            {
                MetaQuestDefinition def;
                if (definitions.TryGetValue(pair.Key, out def) && def.Category == category)
                    doomed.Add(pair.Key);
            }
            for (int i = 0; i < doomed.Count; i++)
                progress.Remove(doomed[i]);
        }
    }
}
