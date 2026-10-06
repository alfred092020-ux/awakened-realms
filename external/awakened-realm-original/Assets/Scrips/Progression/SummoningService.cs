using System;

namespace AwakenedRealm.Progression
{
    /// <summary>
    /// Centralized summoning pity configuration and counter validation.
    /// Pull execution, rates, currency spending, and persistence are
    /// intentionally out of scope for this class.
    /// </summary>
    public static class SummoningService
    {
        public const int LegendarySoftPity = 45;
        public const int LegendaryHardPity = 60;
        public const int MythicSoftPity = 90;
        public const int MythicHardPity = 120;

        /// <summary>A pity counter is valid while 0 &lt;= counter &lt; hardPity.</summary>
        public static bool IsValidPityCounter(int counter, int hardPity)
        {
            if (hardPity <= 0)
                throw new ArgumentOutOfRangeException(nameof(hardPity), hardPity, "Hard pity must be positive.");
            return counter >= 0 && counter < hardPity;
        }

        public static bool IsValidLegendaryPity(int counter)
        {
            return IsValidPityCounter(counter, LegendaryHardPity);
        }

        public static bool IsValidMythicPity(int counter)
        {
            return IsValidPityCounter(counter, MythicHardPity);
        }

        /// <summary>Clamps a possibly-corrupt counter back into the valid range.</summary>
        public static int ClampPityCounter(int counter, int hardPity)
        {
            if (hardPity <= 0)
                throw new ArgumentOutOfRangeException(nameof(hardPity), hardPity, "Hard pity must be positive.");
            if (counter < 0) return 0;
            if (counter >= hardPity) return hardPity - 1;
            return counter;
        }
    }
}
