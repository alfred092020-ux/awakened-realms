using System;
using System.Collections.Generic;

namespace AwakenedRealm.CombatV2
{
    /// <summary>
    /// Immutable rule describing one status or buff: magnitude, duration,
    /// stack cap, and classification. Pure data; no Unity dependency.
    /// </summary>
    public sealed class StatusRule
    {
        public readonly StatusType Type;
        public readonly EffectType Effect;
        public readonly bool IsBuff;
        public readonly int DurationTurns;
        public readonly int MaxStacks;
        public readonly float MagnitudePercent;
        public readonly ScalingStat ScalesWith;

        public StatusRule(
            StatusType type,
            EffectType effect,
            bool isBuff,
            int durationTurns,
            int maxStacks,
            float magnitudePercent,
            ScalingStat scalesWith = ScalingStat.Attack)
        {
            Type = type;
            Effect = effect;
            IsBuff = isBuff;
            DurationTurns = durationTurns;
            MaxStacks = maxStacks;
            MagnitudePercent = magnitudePercent;
            ScalesWith = scalesWith;
        }
    }

    /// <summary>
    /// Centralized canon status rules. Magnitudes are percent values
    /// (e.g. 20 = +20%). Duration is in turns. Stack cap of 1 means
    /// reapplication refreshes duration without stacking.
    /// </summary>
    public static class StatusRules
    {
        static readonly Dictionary<StatusType, StatusRule> Rules =
            new Dictionary<StatusType, StatusRule>
            {
                // Buffs
                { StatusType.AttackUp,      new StatusRule(StatusType.AttackUp,      EffectType.StatModifier, true,  3, 2,  20f, ScalingStat.Attack) },
                { StatusType.DefenseUp,     new StatusRule(StatusType.DefenseUp,     EffectType.StatModifier, true,  3, 1,  25f, ScalingStat.Defense) },
                { StatusType.MagicUp,       new StatusRule(StatusType.MagicUp,       EffectType.StatModifier, true,  3, 2,  20f, ScalingStat.Magic) },
                { StatusType.SpeedUp,       new StatusRule(StatusType.SpeedUp,       EffectType.StatModifier, true,  2, 1,  15f) },
                { StatusType.CritUp,        new StatusRule(StatusType.CritUp,        EffectType.StatModifier, true,  2, 1,  20f) },
                { StatusType.ResistanceUp,  new StatusRule(StatusType.ResistanceUp,  EffectType.StatModifier, true,  3, 1,  25f) },
                { StatusType.HealOverTime,  new StatusRule(StatusType.HealOverTime,  EffectType.HealOverTime, true,  3, 1,  10f, ScalingStat.MaxHealth) },
                { StatusType.Shield,        new StatusRule(StatusType.Shield,        EffectType.Shield,       true,  2, 1,  25f, ScalingStat.MaxHealth) },
                { StatusType.EnergyCharge,  new StatusRule(StatusType.EnergyCharge,  EffectType.Utility,      true,  0, 1,  20f) },

                // Debuffs
                { StatusType.AttackDown,    new StatusRule(StatusType.AttackDown,    EffectType.StatModifier, false, 3, 2, -20f, ScalingStat.Attack) },
                { StatusType.DefenseDown,   new StatusRule(StatusType.DefenseDown,   EffectType.StatModifier, false, 3, 1, -25f, ScalingStat.Defense) },
                { StatusType.MagicDown,     new StatusRule(StatusType.MagicDown,     EffectType.StatModifier, false, 3, 2, -20f, ScalingStat.Magic) },
                { StatusType.SpeedDown,     new StatusRule(StatusType.SpeedDown,     EffectType.StatModifier, false, 2, 1, -15f) },
                { StatusType.CritDown,      new StatusRule(StatusType.CritDown,      EffectType.StatModifier, false, 2, 1, -20f) },
                { StatusType.ResistanceDown,new StatusRule(StatusType.ResistanceDown,EffectType.StatModifier, false, 3, 1, -25f) },
                { StatusType.Burn,          new StatusRule(StatusType.Burn,          EffectType.DamageOverTime, false, 3, 3, 5f, ScalingStat.MaxHealth) },
                { StatusType.Poison,        new StatusRule(StatusType.Poison,        EffectType.DamageOverTime, false, 3, 1, 8f, ScalingStat.MaxHealth) },
                { StatusType.Stun,          new StatusRule(StatusType.Stun,          EffectType.CrowdControl, false, 1, 1, 0f) },
                { StatusType.Silence,       new StatusRule(StatusType.Silence,       EffectType.CrowdControl, false, 2, 1, 0f) },
                { StatusType.Blind,         new StatusRule(StatusType.Blind,         EffectType.CrowdControl, false, 2, 1, -30f) },

                // Extensible statuses declared for hero source compatibility.
                // Root and Bleed have no invented numeric magnitude; callers
                // may attach them and resolve behavior elsewhere.
                { StatusType.Root,          new StatusRule(StatusType.Root,          EffectType.CrowdControl, false, 1, 1, 0f) },
                { StatusType.Bleed,         new StatusRule(StatusType.Bleed,         EffectType.DamageOverTime, false, 2, 1, 0f) },
                { StatusType.Taunt,         new StatusRule(StatusType.Taunt,         EffectType.CrowdControl, false, 2, 1, 0f) }
            };

        public static StatusRule Get(StatusType type)
        {
            StatusRule rule;
            if (Rules.TryGetValue(type, out rule))
                return rule;
            throw new ArgumentOutOfRangeException(nameof(type), type, "No status rule registered.");
        }

        public static bool TryGet(StatusType type, out StatusRule rule)
        {
            return Rules.TryGetValue(type, out rule);
        }

        public static bool IsBuff(StatusType type)
        {
            StatusRule rule;
            return Rules.TryGetValue(type, out rule) && rule.IsBuff;
        }

        public static bool IsDebuff(StatusType type)
        {
            StatusRule rule;
            return Rules.TryGetValue(type, out rule) && !rule.IsBuff;
        }

        /// <summary>
        /// All registered status types in declaration order for deterministic
        /// validation and iteration.
        /// </summary>
        public static IEnumerable<StatusType> AllTypes
        {
            get { return Rules.Keys; }
        }
    }
}
