using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    /// <summary>
    /// Immutable-style reward bundle describing Gold, Gems, SummonTickets,
    /// PlayerXp and arbitrary item quantities keyed by stable item ID.
    /// All values must be nonnegative. Merging produces a new bundle and
    /// never mutates either operand, so grant/rollback stays atomic.
    /// Pure C#: no Unity, persistence, or UI dependencies.
    /// </summary>
    public sealed class MetaRewardBundle
    {
        public static readonly MetaRewardBundle Empty = new MetaRewardBundle(0, 0, 0, 0, null);

        public readonly long Gold;
        public readonly long Gems;
        public readonly long SummonTickets;
        public readonly long PlayerXp;

        // Item quantities keyed by stable item ID. Never null after construction.
        readonly Dictionary<string, long> items;

        public MetaRewardBundle(long gold, long gems, long summonTickets, long playerXp)
            : this(gold, gems, summonTickets, playerXp, null)
        {
        }

        public MetaRewardBundle(
            long gold,
            long gems,
            long summonTickets,
            long playerXp,
            IDictionary<string, long> items)
        {
            if (gold < 0 || gems < 0 || summonTickets < 0 || playerXp < 0)
                throw new ArgumentOutOfRangeException("reward", "Reward currency values must be nonnegative.");
            if (items == null || items.Count == 0)
            {
                this.items = new Dictionary<string, long>(StringComparer.Ordinal);
            }
            else
            {
                this.items = new Dictionary<string, long>(items.Count, StringComparer.Ordinal);
                foreach (KeyValuePair<string, long> pair in items)
                {
                    if (string.IsNullOrEmpty(pair.Key))
                        throw new ArgumentException("Item IDs must be nonempty stable strings.", nameof(items));
                    if (pair.Value < 0)
                        throw new ArgumentOutOfRangeException("items", "Item quantities must be nonnegative.");
                    if (pair.Value == 0)
                        continue; // normalize zero-quantity entries away
                    this.items.Add(pair.Key, pair.Value);
                }
            }

            Gold = gold;
            Gems = gems;
            SummonTickets = summonTickets;
            PlayerXp = playerXp;
        }

        /// <summary>Read-only view of item quantities keyed by stable item ID.</summary>
        public IReadOnlyDictionary<string, long> Items
        {
            get { return items; }
        }

        public long ItemQuantity(string itemId)
        {
            long value;
            return items.TryGetValue(itemId, out value) ? value : 0L;
        }

        public bool IsEmpty
        {
            get
            {
                return Gold == 0 && Gems == 0 && SummonTickets == 0 && PlayerXp == 0 && items.Count == 0;
            }
        }

        /// <summary>
        /// Returns a new bundle whose fields are the sum of this bundle and
        /// <paramref name="other"/>. Neither operand is mutated.
        /// </summary>
        public MetaRewardBundle Merge(MetaRewardBundle other)
        {
            if (other == null)
                throw new ArgumentNullException(nameof(other));

            var merged = new Dictionary<string, long>(items, StringComparer.Ordinal);
            foreach (KeyValuePair<string, long> pair in other.items)
            {
                long existing;
                merged.TryGetValue(pair.Key, out existing);
                merged[pair.Key] = checked(existing + pair.Value);
            }

            return new MetaRewardBundle(
                checked(Gold + other.Gold),
                checked(Gems + other.Gems),
                checked(SummonTickets + other.SummonTickets),
                checked(PlayerXp + other.PlayerXp),
                merged);
        }
    }
}
