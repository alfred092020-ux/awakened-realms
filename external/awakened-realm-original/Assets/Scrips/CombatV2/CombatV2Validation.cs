using System;
using System.Collections.Generic;

namespace AwakenedRealm.CombatV2
{
    /// <summary>
    /// Deterministic integrity checks over the CombatV2 domain: catalog
    /// completeness, ability shape, targeting references, and slot validity.
    /// Pure C#; safe to run from editor validation or headless harnesses.
    /// </summary>
    public static class CombatV2Validation
    {
        public sealed class Report
        {
            public int HeroCount;
            public int AbilityCount;
            public int CheckCount;
            public bool Success => Failures.Count == 0;
            public readonly List<string> Failures = new List<string>();

            public string Summary()
            {
                return string.Format(
                    "CombatV2: {0} heroes, {1} abilities, {2} checks, {3} failures",
                    HeroCount, AbilityCount, CheckCount, Failures.Count);
            }
        }

        /// <summary>
        /// Run all deterministic checks. Returns a report; throws nothing on
        /// validation failure (callers inspect <see cref="Report.Success"/>).
        /// </summary>
        public static Report Run()
        {
            var report = new Report();

            CheckUniqueKitCount(report);
            CheckAbilitySlots(report);
            CheckAbilityTargeting(report);
            CheckStatusReferences(report);
            CheckSlotValidity(report);

            return report;
        }

        static void CheckUniqueKitCount(Report report)
        {
            report.HeroCount = HeroKitCatalog.Count;
            Assert(report, HeroKitCatalog.Count == 12, "Expected exactly 12 hero kits, found " + HeroKitCatalog.Count);

            var seen = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < HeroKitCatalog.All.Count; i++)
            {
                var kit = HeroKitCatalog.All[i];
                Assert(report, seen.Add(kit.Id), "Duplicate hero kit id " + kit.Id);
                report.CheckCount++;
            }
        }

        static void CheckAbilitySlots(Report report)
        {
            var required = new[] { AbilitySlot.Basic, AbilitySlot.Skill, AbilitySlot.Passive, AbilitySlot.Ultimate };
            for (int i = 0; i < HeroKitCatalog.All.Count; i++)
            {
                var kit = HeroKitCatalog.All[i];
                Assert(report, kit.Abilities.Count == 4, kit.Id + " must have exactly 4 abilities");
                report.AbilityCount += kit.Abilities.Count;

                var slots = new HashSet<AbilitySlot>();
                for (int a = 0; a < kit.Abilities.Count; a++)
                {
                    var ability = kit.Abilities[a];
                    Assert(report, slots.Add(ability.Slot), kit.Id + " duplicate ability slot " + ability.Slot);
                    Assert(report, !string.IsNullOrWhiteSpace(ability.Id), kit.Id + " ability id required");
                    Assert(report, !string.IsNullOrWhiteSpace(ability.Name), kit.Id + "." + ability.Id + " name required");
                    report.CheckCount++;
                }

                for (int s = 0; s < required.Length; s++)
                {
                    Assert(report, slots.Contains(required[s]), kit.Id + " missing slot " + required[s]);
                    report.CheckCount++;
                }
            }
        }

        static void CheckAbilityTargeting(Report report)
        {
            for (int i = 0; i < HeroKitCatalog.All.Count; i++)
            {
                var kit = HeroKitCatalog.All[i];
                for (int a = 0; a < kit.Abilities.Count; a++)
                {
                    var ability = kit.Abilities[a];
                    Assert(report, Enum.IsDefined(typeof(TargetPattern), ability.Target),
                        kit.Id + "." + ability.Id + " invalid target pattern");
                    Assert(report, Enum.IsDefined(typeof(ScalingStat), ability.Scaling),
                        kit.Id + "." + ability.Id + " invalid scaling stat");
                    Assert(report, ability.DamageCoefficient >= 0f && ability.HealCoefficient >= 0f,
                        kit.Id + "." + ability.Id + " negative coefficient");
                    Assert(report, ability.ProcChance >= 0f && ability.ProcChance <= 1f,
                        kit.Id + "." + ability.Id + " proc chance out of range");
                    Assert(report, ability.SplashCoefficient >= 0f && ability.SplashCoefficient <= 1f,
                        kit.Id + "." + ability.Id + " splash coefficient out of range");
                    Assert(report, ability.ShieldFromMaxHealthPercent >= 0f && ability.ShieldFromMaxHealthPercent <= 1f,
                        kit.Id + "." + ability.Id + " shield max-HP percent out of range");
                    Assert(report, ability.ShieldFromDefensePercent >= 0f && ability.ShieldFromDefensePercent <= 1f,
                        kit.Id + "." + ability.Id + " shield DEF percent out of range");
                    Assert(report, ability.HealFromDamageDealtPercent >= 0f && ability.HealFromDamageDealtPercent <= 1f,
                        kit.Id + "." + ability.Id + " heal-from-damage percent out of range");
                    Assert(report, ability.PierceCount >= 0 && ability.PierceCount <= FormationGrid.SlotCount,
                        kit.Id + "." + ability.Id + " pierce count out of range");
                    report.CheckCount++;
                }
            }
        }

        static void CheckStatusReferences(Report report)
        {
            for (int i = 0; i < HeroKitCatalog.All.Count; i++)
            {
                var kit = HeroKitCatalog.All[i];
                for (int a = 0; a < kit.Abilities.Count; a++)
                {
                    var ability = kit.Abilities[a];
                    for (int s = 0; s < ability.Statuses.Count; s++)
                    {
                        var payload = ability.Statuses[s];
                        Assert(report, payload.Status != StatusType.None,
                            kit.Id + "." + ability.Id + " status payload with StatusType.None");
                        Assert(report, Enum.IsDefined(typeof(StatusType), payload.Status),
                            kit.Id + "." + ability.Id + " invalid status type");
                        Assert(report, payload.ProcChance >= 0f && payload.ProcChance <= 1f,
                            kit.Id + "." + ability.Id + " status proc chance out of range");
                        Assert(report, payload.MagnitudeOverridePercent >= -100f && payload.MagnitudeOverridePercent <= 100f,
                            kit.Id + "." + ability.Id + " magnitude override out of range");

                        StatusRule rule;
                        Assert(report, StatusRules.TryGet(payload.Status, out rule),
                            kit.Id + "." + ability.Id + " references unregistered status " + payload.Status);
                        if (rule != null && payload.DurationTurns > 0)
                        {
                            Assert(report, payload.DurationTurns <= rule.DurationTurns + 1,
                                kit.Id + "." + ability.Id + " duration exceeds rule bound for " + payload.Status);
                        }
                        report.CheckCount++;
                    }
                }
            }
        }

        static void CheckSlotValidity(Report report)
        {
            for (int slot = 0; slot < FormationGrid.SlotCount; slot++)
            {
                Assert(report, FormationGrid.IsValidSlot(slot), "Slot " + slot + " reported invalid");
                Assert(report, FormationGrid.SlotOf(FormationGrid.RowOf(slot), FormationGrid.ColumnOf(slot)) == slot,
                    "Slot " + slot + " row/column round-trip failed");
                report.CheckCount++;
            }

            Assert(report, !FormationGrid.IsValidSlot(-1), "Slot -1 accepted");
            Assert(report, !FormationGrid.IsValidSlot(FormationGrid.SlotCount), "Slot " + FormationGrid.SlotCount + " accepted");
            report.CheckCount += 2;
        }

        static void Assert(Report report, bool condition, string message)
        {
            if (!condition)
                report.Failures.Add(message);
        }
    }
}
