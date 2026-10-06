using System;

namespace AwakenedRealm.Progression
{
    /// <summary>
    /// Tunable idle-reward configuration. Rates are expressed per minute and
    /// resolved with integer-only math so results are deterministic on every
    /// runtime. The offline duration cap defaults to 12 hours.
    /// </summary>
    public sealed class IdleRewardConfig
    {
        // Gold per minute = BaseGoldPerMinute + GoldPerMinutePerStage * stageIndex.
        // stageIndex counts cleared stages (0..120), so stage 0 still earns the
        // onboarding-safe baseline and the rate grows monotonically.
        public int BaseGoldPerMinute = 10;
        public int GoldPerMinutePerStage = 2;
        public int BasePlayerXpPerMinute = 4;
        public int PlayerXpPerMinutePerStage = 1;
        public long MaxOfflineMinutes = 12 * 60;

        public void Validate()
        {
            if (BaseGoldPerMinute < 0 || GoldPerMinutePerStage < 0 ||
                BasePlayerXpPerMinute < 0 || PlayerXpPerMinutePerStage < 0)
                throw new InvalidOperationException("Idle reward rates cannot be negative.");
            if (MaxOfflineMinutes < 0)
                throw new InvalidOperationException("Idle reward cap cannot be negative.");
        }
    }

    /// <summary>The deterministic reward earned over an offline interval.</summary>
    public sealed class IdleReward
    {
        public int Gold;
        public int PlayerXp;
        public long MinutesCounted;
        public bool Capped;
    }

    /// <summary>
    /// Pure idle-reward math. Preview never mutates state; Claim performs the
    /// calculate-then-commit sequence exactly once so it is atomic.
    /// </summary>
    public static class IdleRewards
    {
        /// <summary>
        /// Returns the reward that would be granted for the offline interval
        /// ending at <paramref name="nowUtc"/>. Does not modify state.
        /// </summary>
        public static IdleReward Preview(GameProgressionState state, DateTime nowUtc,
            IdleRewardConfig config = null)
        {
            if (state == null) throw new ArgumentNullException(nameof(state));
            if (config == null) config = new IdleRewardConfig();
            config.Validate();

            long minutes = OfflineMinutes(state, nowUtc, config, out bool capped);
            return Calculate(state.HighestClearedStage, minutes, capped, config);
        }

        /// <summary>
        /// Grants the pending idle reward and stamps LastSeenUtc with
        /// <paramref name="nowUtc"/>. A first-ever claim (unset timestamp) or a
        /// non-increasing clock grants zero reward; the clock never moves
        /// backwards.
        /// </summary>
        public static IdleReward Claim(GameProgressionState state, DateTime nowUtc,
            IdleRewardConfig config = null)
        {
            if (state == null) throw new ArgumentNullException(nameof(state));
            if (config == null) config = new IdleRewardConfig();
            config.Validate();

            long nowTicks = nowUtc.ToUniversalTime().Ticks;

            // No prior session or a backwards clock: grant nothing. Only the
            // first claim establishes the timestamp; time never rewinds.
            if (state.LastSeenUtcTicks <= 0)
            {
                state.LastSeenUtcTicks = nowTicks;
                return new IdleReward();
            }
            if (nowTicks <= state.LastSeenUtcTicks)
                return new IdleReward();

            IdleReward reward = Preview(state, nowUtc, config);
            state.Gold = SaturatingAdd(state.Gold, reward.Gold);
            state.PlayerXp = SaturatingAdd(state.PlayerXp, reward.PlayerXp);
            state.LastSeenUtcTicks = nowTicks;
            return reward;
        }

        static long OfflineMinutes(GameProgressionState state, DateTime nowUtc,
            IdleRewardConfig config, out bool capped)
        {
            capped = false;
            if (state.LastSeenUtcTicks <= 0)
                return 0;

            long nowTicks = nowUtc.ToUniversalTime().Ticks;
            long elapsedTicks = nowTicks - state.LastSeenUtcTicks;
            if (elapsedTicks <= 0)
                return 0;

            long minutes = elapsedTicks / TimeSpan.TicksPerMinute;
            if (minutes > config.MaxOfflineMinutes)
            {
                minutes = config.MaxOfflineMinutes;
                capped = true;
            }
            return minutes;
        }

        static IdleReward Calculate(int highestClearedStage, long minutes, bool capped,
            IdleRewardConfig config)
        {
            if (minutes <= 0)
                return new IdleReward { Capped = capped };

            // Count cleared stages, not the raw stage ID: the rate grows
            // monotonically with progress and stays dense across the
            // chapter * 100 + index ID scheme.
            long stageIndex = Math.Max(0, ClearedStageCount(highestClearedStage));

            long gold = (config.BaseGoldPerMinute + config.GoldPerMinutePerStage * stageIndex) * minutes;
            long xp = (config.BasePlayerXpPerMinute + config.PlayerXpPerMinutePerStage * stageIndex) * minutes;

            return new IdleReward
            {
                Gold = (int)Math.Min(int.MaxValue, Math.Max(0, gold)),
                PlayerXp = (int)Math.Min(int.MaxValue, Math.Max(0, xp)),
                MinutesCounted = minutes,
                Capped = capped
            };
        }

        /// <summary>Number of catalog stages cleared when the given stage ID is the highest cleared.</summary>
        public static int ClearedStageCount(int highestClearedStage)
        {
            if (highestClearedStage <= 0)
                return 0;

            CampaignStage[] stages = CampaignCatalog.Stages;
            int lo = 0;
            int hi = stages.Length; // count of stages with ID <= highestClearedStage
            while (lo < hi)
            {
                int mid = lo + (hi - lo) / 2;
                if (stages[mid].StageId <= highestClearedStage)
                    lo = mid + 1;
                else
                    hi = mid;
            }
            return lo;
        }

        static int SaturatingAdd(int current, int delta)
        {
            long sum = (long)current + delta;
            if (sum < 0) return 0;
            if (sum > int.MaxValue) return int.MaxValue;
            return (int)sum;
        }
    }
}
