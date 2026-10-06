using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    /// <summary>
    /// Immutable tower floor definition. Floor IDs are stable integers 1..100;
    /// every 10th floor is a boss floor with a richer first-clear reward.
    /// </summary>
    public sealed class MetaTowerFloor
    {
        public readonly int FloorId;
        public readonly bool IsBossFloor;
        public readonly MetaRewardBundle FirstClearReward;
        public readonly long RecommendedPower;

        public MetaTowerFloor(int floorId, bool isBossFloor, MetaRewardBundle firstClearReward, long recommendedPower)
        {
            if (floorId < 1)
                throw new ArgumentOutOfRangeException(nameof(floorId), "Floor IDs start at 1.");
            if (firstClearReward == null)
                throw new ArgumentNullException(nameof(firstClearReward));
            if (recommendedPower < 0)
                throw new ArgumentOutOfRangeException(nameof(recommendedPower), "Recommended power must be nonnegative.");

            FloorId = floorId;
            IsBossFloor = isBossFloor;
            FirstClearReward = firstClearReward;
            RecommendedPower = recommendedPower;
        }
    }

    /// <summary>
    /// Deterministic 100-floor tower catalog. Floors are numbered 1..100 and
    /// every floor divisible by 10 is a boss floor. First-clear rewards scale
    /// linearly with the floor index; boss floors use a higher tier.
    /// Pure data: no randomness, no wall-clock reads.
    /// </summary>
    public static class MetaTowerCatalog
    {
        public const int FloorCount = 100;
        public const int BossFloorInterval = 10;

        static readonly MetaTowerFloor[] OrderedFloors;
        static readonly Dictionary<int, MetaTowerFloor> ById;

        static MetaTowerCatalog()
        {
            OrderedFloors = new MetaTowerFloor[FloorCount];
            ById = new Dictionary<int, MetaTowerFloor>(FloorCount);
            for (int floor = 1; floor <= FloorCount; floor++)
            {
                bool isBoss = floor % BossFloorInterval == 0;
                // Deterministic linear reward ramp; boss floors pay 5x plus a ticket.
                MetaRewardBundle reward = isBoss
                    ? new MetaRewardBundle(500L * floor, 50L * floor, 1, 250L * floor)
                    : new MetaRewardBundle(100L * floor, 10L * floor, 0, 50L * floor);
                var f = new MetaTowerFloor(floor, isBoss, reward, 1000L * floor);
                OrderedFloors[floor - 1] = f;
                ById.Add(floor, f);
            }
        }

        public static bool IsFloor(int floorId)
        {
            return floorId >= 1 && floorId <= FloorCount;
        }

        public static bool IsBossFloor(int floorId)
        {
            return IsFloor(floorId) && floorId % BossFloorInterval == 0;
        }

        public static MetaTowerFloor GetFloor(int floorId)
        {
            MetaTowerFloor floor;
            if (!ById.TryGetValue(floorId, out floor))
                throw new ArgumentOutOfRangeException(nameof(floorId), floorId, "Unknown tower floor ID.");
            return floor;
        }

        /// <summary>Floor the player may attempt next; 0 when the tower is complete.</summary>
        public static int NextFloorAfter(int highestClearedFloor)
        {
            if (highestClearedFloor < 0 || highestClearedFloor >= FloorCount)
                return 0;
            return highestClearedFloor + 1;
        }
    }

    /// <summary>
    /// Mutable tower progression state. Tracks the monotonic highest-cleared
    /// floor; floors cannot be skipped and first-clear rewards are granted
    /// exactly once per floor.
    /// </summary>
    [Serializable]
    public sealed class MetaTowerProgress
    {
        /// <summary>Highest floor cleared so far; 0 = none cleared.</summary>
        public int HighestClearedFloor;

        /// <summary>The next floor the player may attempt (0 = tower complete).</summary>
        public int NextFloor
        {
            get { return MetaTowerCatalog.NextFloorAfter(HighestClearedFloor); }
        }

        /// <summary>
        /// Records a clear of <paramref name="floorId"/>. Only the exact next
        /// floor is accepted, so skipping is impossible. The returned reward
        /// is the floor's first-clear bundle; repeat attempts fail.
        /// </summary>
        public bool TryClearFloor(int floorId, out MetaRewardBundle firstClearReward)
        {
            firstClearReward = null;
            int next = NextFloor;
            if (next == 0 || floorId != next)
                return false;

            MetaTowerFloor floor = MetaTowerCatalog.GetFloor(floorId);
            HighestClearedFloor = floorId;
            firstClearReward = floor.FirstClearReward;
            return true;
        }
    }
}
