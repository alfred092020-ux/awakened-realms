using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    /// <summary>
    /// Immutable 7-day repeating login reward calendar. Day indices are 1..7
    /// and the cycle repeats: day 8 maps back to slot 1.
    /// </summary>
    public sealed class MetaDailyLoginCalendar
    {
        public const int CycleLength = 7;

        readonly MetaRewardBundle[] dayRewards;

        /// <param name="cycleRewards">Exactly 7 bundles, in day order 1..7.</param>
        public MetaDailyLoginCalendar(IReadOnlyList<MetaRewardBundle> cycleRewards)
        {
            if (cycleRewards == null || cycleRewards.Count != CycleLength)
                throw new ArgumentException("Calendar requires exactly 7 day rewards.", nameof(cycleRewards));
            dayRewards = new MetaRewardBundle[CycleLength];
            for (int i = 0; i < CycleLength; i++)
            {
                if (cycleRewards[i] == null)
                    throw new ArgumentException("Calendar rewards must not contain nulls.", nameof(cycleRewards));
                dayRewards[i] = cycleRewards[i];
            }
        }

        /// <summary>Reward for the deterministic cycle day (1-based day index).</summary>
        public MetaRewardBundle RewardForCycleDay(int cycleDay)
        {
            if (cycleDay < 1)
                throw new ArgumentOutOfRangeException(nameof(cycleDay), cycleDay, "Cycle day is 1-based.");
            return dayRewards[(cycleDay - 1) % CycleLength];
        }
    }

    /// <summary>
    /// Mutable daily-login tracker. The caller supplies explicit UTC day keys
    /// (e.g. "2026-10-05"); no wall-clock reads happen here. The same day key
    /// cannot claim twice, and a missed day simply leaves the streak where it
    /// was - the cycle day advances only on successful claims.
    /// </summary>
    [Serializable]
    public sealed class MetaDailyLoginState
    {
        /// <summary>UTC day key of the most recent successful claim; empty = never claimed.</summary>
        public string LastClaimedDayKey = string.Empty;

        /// <summary>Number of days ever claimed. Determines the next cycle slot.</summary>
        public int TotalClaims;

        /// <summary>Next cycle day index (1..7) the player will receive.</summary>
        public int NextCycleDay
        {
            get { return (TotalClaims % MetaDailyLoginCalendar.CycleLength) + 1; }
        }

        /// <summary>Reward the player will receive on the next successful claim.</summary>
        public MetaRewardBundle PeekNextReward(MetaDailyLoginCalendar calendar)
        {
            if (calendar == null)
                throw new ArgumentNullException(nameof(calendar));
            return calendar.RewardForCycleDay(NextCycleDay);
        }

        /// <summary>
        /// Attempts to claim today's login reward for <paramref name="utcDayKey"/>.
        /// Returns false when that key was already claimed. Any other key is a
        /// new claim day; consecutive or skipped days both simply advance the
        /// deterministic cycle slot.
        /// </summary>
        public bool TryClaim(MetaDailyLoginCalendar calendar, string utcDayKey, out MetaRewardBundle reward)
        {
            if (calendar == null)
                throw new ArgumentNullException(nameof(calendar));
            if (string.IsNullOrEmpty(utcDayKey))
                throw new ArgumentException("Day key must be nonempty (e.g. \"2026-10-05\").", nameof(utcDayKey));

            reward = null;
            if (string.Equals(LastClaimedDayKey, utcDayKey, StringComparison.Ordinal))
                return false;

            reward = calendar.RewardForCycleDay(NextCycleDay);
            LastClaimedDayKey = utcDayKey;
            TotalClaims++;
            return true;
        }
    }
}
