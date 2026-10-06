using System;
using System.Collections.Generic;

namespace AwakenedRealm.CombatV2
{
    /// <summary>
    /// A single status application attached to an ability.
    /// </summary>
    public sealed class StatusPayload
    {
        public readonly StatusType Status;
        public readonly float ProcChance;
        public readonly int DurationTurns;

        /// <summary>
        /// Hero-authored magnitude override in percent. A value of 0 means
        /// "use the centralized <see cref="StatusRules"/> default". Nonzero
        /// preserves kit-specific deviations (e.g. a skill granting +10% ATK
        /// while generic AttackUp is +20%).
        /// </summary>
        public readonly float MagnitudeOverridePercent;

        /// <summary>
        /// When true the payload targets the caster's side rather than
        /// the ability's resolved target set (used for self buffs).
        /// </summary>
        public readonly bool ApplyToCasterSide;

        public StatusPayload(
            StatusType status,
            float procChance = 1f,
            int durationTurns = -1,
            float magnitudeOverridePercent = 0f,
            bool applyToCasterSide = false)
        {
            Status = status;
            ProcChance = procChance;
            DurationTurns = durationTurns;
            MagnitudeOverridePercent = magnitudeOverridePercent;
            ApplyToCasterSide = applyToCasterSide;
        }

        /// <summary>
        /// Effective magnitude in percent: the override when present,
        /// otherwise the canonical rule magnitude.
        /// </summary>
        public float EffectiveMagnitudePercent()
        {
            if (MagnitudeOverridePercent != 0f)
                return MagnitudeOverridePercent;
            StatusRule rule;
            return StatusRules.TryGet(Status, out rule) ? rule.MagnitudePercent : 0f;
        }
    }

    /// <summary>
    /// Immutable ability definition. Coefficients are multipliers of the
    /// caster's scaling stat (e.g. 1.10 = 110% MAG). A damage coefficient
    /// of 0 with a heal coefficient of 0 means the ability is pure utility.
    /// </summary>
    public sealed class AbilityDefinition
    {
        public readonly string Id;
        public readonly string Name;
        public readonly AbilitySlot Slot;
        public readonly TargetPattern Target;
        public readonly ScalingStat Scaling;
        public readonly float DamageCoefficient;
        public readonly float HealCoefficient;
        public readonly float ProcChance;
        public readonly int DurationTurns;
        public readonly bool GuaranteedCrit;
        public readonly bool CleansesDebuffs;
        public readonly bool GrantsExtraTurn;
        public readonly int PierceCount;
        public readonly float SplashCoefficient;
        public readonly float ShieldFromMaxHealthPercent;
        public readonly float ShieldFromDefensePercent;
        public readonly float HealFromDamageDealtPercent;
        public readonly IReadOnlyList<StatusPayload> Statuses;
        public readonly string Notes;

        public AbilityDefinition(
            string id,
            string name,
            AbilitySlot slot,
            TargetPattern target,
            ScalingStat scaling,
            float damageCoefficient = 0f,
            float healCoefficient = 0f,
            float procChance = 0f,
            int durationTurns = 0,
            bool guaranteedCrit = false,
            bool cleansesDebuffs = false,
            bool grantsExtraTurn = false,
            int pierceCount = 0,
            float splashCoefficient = 0f,
            float shieldFromMaxHealthPercent = 0f,
            float shieldFromDefensePercent = 0f,
            float healFromDamageDealtPercent = 0f,
            IReadOnlyList<StatusPayload> statuses = null,
            string notes = "")
        {
            if (string.IsNullOrWhiteSpace(id))
                throw new ArgumentException("Ability id is required.", nameof(id));
            if (string.IsNullOrWhiteSpace(name))
                throw new ArgumentException("Ability name is required.", nameof(name));

            Id = id;
            Name = name;
            Slot = slot;
            Target = target;
            Scaling = scaling;
            DamageCoefficient = damageCoefficient;
            HealCoefficient = healCoefficient;
            ProcChance = procChance;
            DurationTurns = durationTurns;
            GuaranteedCrit = guaranteedCrit;
            CleansesDebuffs = cleansesDebuffs;
            GrantsExtraTurn = grantsExtraTurn;
            PierceCount = pierceCount;
            SplashCoefficient = splashCoefficient;
            ShieldFromMaxHealthPercent = shieldFromMaxHealthPercent;
            ShieldFromDefensePercent = shieldFromDefensePercent;
            HealFromDamageDealtPercent = healFromDamageDealtPercent;
            Statuses = statuses ?? Array.Empty<StatusPayload>();
            Notes = notes ?? string.Empty;
        }
    }
}
