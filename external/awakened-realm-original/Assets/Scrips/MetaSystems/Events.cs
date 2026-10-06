using System;
using System.Collections.Generic;

namespace AwakenedRealm.MetaSystems
{
    /// <summary>
    /// Immutable live-event definition. Window is expressed as UTC ticks from
    /// data; <see cref="IsActive"/> is a pure function of the caller-supplied
    /// now. Modifiers are integer basis-point multipliers keyed by stable
    /// modifier name (e.g. "gold_gain_bp": 11000 = +10%). RewardTableKeys
    /// reference deterministic reward tables owned elsewhere.
    /// </summary>
    public sealed class MetaEventDefinition
    {
        /// <summary>Scaling denominator for modifier basis points.</summary>
        public const int BasisPointDenominator = 10000;

        public readonly string EventId;
        public readonly long StartUtcTicks;
        public readonly long EndUtcTicks;
        public readonly bool Enabled;

        readonly Dictionary<string, int> modifiers;
        readonly string[] rewardTableKeys;

        public MetaEventDefinition(
            string eventId,
            long startUtcTicks,
            long endUtcTicks,
            bool enabled,
            IDictionary<string, int> modifiers,
            IEnumerable<string> rewardTableKeys)
        {
            if (string.IsNullOrEmpty(eventId))
                throw new ArgumentException("Event ID must be a nonempty stable string.", nameof(eventId));
            if (endUtcTicks <= startUtcTicks)
                throw new ArgumentException("Event window must end after it starts.", nameof(endUtcTicks));

            EventId = eventId;
            StartUtcTicks = startUtcTicks;
            EndUtcTicks = endUtcTicks;
            Enabled = enabled;

            this.modifiers = new Dictionary<string, int>(StringComparer.Ordinal);
            if (modifiers != null)
            {
                foreach (KeyValuePair<string, int> pair in modifiers)
                {
                    if (string.IsNullOrEmpty(pair.Key))
                        throw new ArgumentException("Modifier keys must be nonempty.", nameof(modifiers));
                    this.modifiers.Add(pair.Key, pair.Value);
                }
            }

            var keys = new List<string>();
            if (rewardTableKeys != null)
            {
                foreach (string key in rewardTableKeys)
                {
                    if (string.IsNullOrEmpty(key))
                        throw new ArgumentException("Reward table keys must be nonempty.", nameof(rewardTableKeys));
                    keys.Add(key);
                }
            }
            this.rewardTableKeys = keys.ToArray();
        }

        /// <summary>Read-only view of basis-point modifiers.</summary>
        public IReadOnlyDictionary<string, int> Modifiers
        {
            get { return modifiers; }
        }

        /// <summary>Stable reward-table keys referenced by this event.</summary>
        public IReadOnlyList<string> RewardTableKeys
        {
            get { return rewardTableKeys; }
        }

        public DateTime StartUtc
        {
            get { return new DateTime(StartUtcTicks, DateTimeKind.Utc); }
        }

        public DateTime EndUtc
        {
            get { return new DateTime(EndUtcTicks, DateTimeKind.Utc); }
        }

        /// <summary>
        /// Pure activity check: enabled and nowUtcTicks in [start, end).
        /// </summary>
        public bool IsActive(long nowUtcTicks)
        {
            return Enabled && nowUtcTicks >= StartUtcTicks && nowUtcTicks < EndUtcTicks;
        }

        /// <summary>Basis-point modifier value (0 when undefined).</summary>
        public int ModifierBp(string key)
        {
            int value;
            return modifiers.TryGetValue(key, out value) ? value : 0;
        }

        /// <summary>Convenience multiplier for a modifier: 1.0 when undefined.</summary>
        public double ModifierMultiplier(string key)
        {
            return (double)ModifierBp(key) / BasisPointDenominator;
        }
    }

    /// <summary>
    /// Validated catalog of event definitions. Rejects duplicate IDs and
    /// invalid windows at construction; offers pure active-event queries.
    /// </summary>
    public sealed class MetaEventCatalog
    {
        readonly Dictionary<string, MetaEventDefinition> events =
            new Dictionary<string, MetaEventDefinition>(StringComparer.Ordinal);
        readonly List<MetaEventDefinition> ordered = new List<MetaEventDefinition>();

        public MetaEventCatalog(IEnumerable<MetaEventDefinition> defs)
        {
            if (defs == null)
                throw new ArgumentNullException(nameof(defs));
            foreach (MetaEventDefinition def in defs)
            {
                if (def == null)
                    throw new ArgumentException("Event catalog must not contain null entries.", nameof(defs));
                if (events.ContainsKey(def.EventId))
                    throw new InvalidOperationException("Duplicate event ID: " + def.EventId);
                events.Add(def.EventId, def);
                ordered.Add(def);
            }
        }

        public IReadOnlyDictionary<string, MetaEventDefinition> Events
        {
            get { return events; }
        }

        /// <summary>All events in catalog-declaration order.</summary>
        public IReadOnlyList<MetaEventDefinition> Ordered
        {
            get { return ordered; }
        }

        /// <summary>
        /// Active events at <paramref name="nowUtcTicks"/>, in catalog order.
        /// </summary>
        public List<MetaEventDefinition> ActiveAt(long nowUtcTicks)
        {
            var active = new List<MetaEventDefinition>();
            for (int i = 0; i < ordered.Count; i++)
            {
                if (ordered[i].IsActive(nowUtcTicks))
                    active.Add(ordered[i]);
            }
            return active;
        }

        /// <summary>Combined basis-point multiplier for a modifier across active events.</summary>
        public int CombinedModifierBp(string key, long nowUtcTicks)
        {
            long combined = MetaEventDefinition.BasisPointDenominator;
            foreach (MetaEventDefinition e in ordered)
            {
                if (!e.IsActive(nowUtcTicks))
                    continue;
                int bp = e.ModifierBp(key);
                if (bp != 0)
                    combined = checked(combined * bp / MetaEventDefinition.BasisPointDenominator);
            }
            if (combined > int.MaxValue)
                combined = int.MaxValue;
            return (int)combined;
        }
    }
}
