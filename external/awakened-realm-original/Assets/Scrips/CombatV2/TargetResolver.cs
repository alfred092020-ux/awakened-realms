using System;
using System.Collections.Generic;

namespace AwakenedRealm.CombatV2
{
    /// <summary>
    /// Pure, deterministic resolution of ability targeting patterns against
    /// the stable 3x3 formation grid. No randomness; ties are broken by
    /// lowest slot index.
    /// </summary>
    public static class TargetResolver
    {
        /// <summary>
        /// Resolve a target pattern for a caster at a given slot.
        /// </summary>
        /// <param name="pattern">Pattern to resolve.</param>
        /// <param name="caster">The unit using the ability.</param>
        /// <param name="allUnits">All units on the battlefield.</param>
        /// <param name="selectedTargetSlot">
        /// For single-target patterns, the slot the player chose. Ignored for
        /// self, all, row, column, adjacent, and lowest-health patterns.
        /// </param>
        /// <returns>Ordered list of affected units; may be empty.</returns>
        public static IReadOnlyList<CombatUnit> Resolve(
            TargetPattern pattern,
            CombatUnit caster,
            IReadOnlyList<CombatUnit> allUnits,
            int selectedTargetSlot = -1)
        {
            if (caster == null)
                throw new ArgumentNullException(nameof(caster));
            if (allUnits == null)
                throw new ArgumentNullException(nameof(allUnits));

            switch (pattern)
            {
                case TargetPattern.None:
                    return Array.Empty<CombatUnit>();

                case TargetPattern.Self:
                    return new[] { caster };

                case TargetPattern.SingleEnemy:
                    return SingleEnemy(caster, allUnits, selectedTargetSlot);

                case TargetPattern.SingleAlly:
                    return SingleAlly(caster, allUnits, selectedTargetSlot);

                case TargetPattern.RowEnemies:
                    return ByRow(caster, allUnits, selectedTargetSlot);

                case TargetPattern.ColumnEnemies:
                    return ByColumn(caster, allUnits, selectedTargetSlot);

                case TargetPattern.AdjacentEnemies:
                    return AdjacentEnemies(caster, allUnits, selectedTargetSlot);

                case TargetPattern.AllEnemies:
                    return AliveEnemies(caster, allUnits);

                case TargetPattern.AllAllies:
                    return AliveAllies(caster, allUnits);

                case TargetPattern.LowestHealthEnemy:
                    return LowestHealth(caster, allUnits, enemiesOnly: true);

                case TargetPattern.LowestHealthAlly:
                    return LowestHealth(caster, allUnits, enemiesOnly: false);

                default:
                    throw new ArgumentOutOfRangeException(nameof(pattern), pattern, "Unsupported target pattern.");
            }
        }

        /// <summary>
        /// Choose the preferred protection target for a defender guarding its
        /// team: the alive Defender with the lowest slot index. This API is
        /// explicit; callers opt in to protection behavior rather than relying
        /// on hidden randomness.
        /// </summary>
        public static CombatUnit PreferredProtectionTarget(IReadOnlyList<CombatUnit> allUnits, CombatTeam team)
        {
            CombatUnit best = null;
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit == null || !unit.IsAlive || unit.Team != team || unit.Role != HeroRole.Defender)
                    continue;
                if (best == null || unit.Slot < best.Slot)
                    best = unit;
            }
            return best;
        }

        /// <summary>
        /// Slot-validity check used by validation and UI layers.
        /// </summary>
        public static bool IsSelectableEnemySlot(int slot, IReadOnlyList<CombatUnit> allUnits, CombatTeam casterTeam)
        {
            if (!FormationGrid.IsValidSlot(slot))
                return false;
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit != null && unit.IsAlive && unit.Team != casterTeam && unit.Slot == slot)
                    return true;
            }
            return false;
        }

        static IReadOnlyList<CombatUnit> SingleEnemy(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits, int targetSlot)
        {
            if (!FormationGrid.IsValidSlot(targetSlot))
                return Array.Empty<CombatUnit>();
            var unit = FindAtSlot(allUnits, targetSlot, CombatTeam.Hero == caster.Team ? CombatTeam.Enemy : CombatTeam.Hero);
            return unit != null && unit.IsAlive ? new[] { unit } : Array.Empty<CombatUnit>();
        }

        static IReadOnlyList<CombatUnit> SingleAlly(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits, int targetSlot)
        {
            if (!FormationGrid.IsValidSlot(targetSlot))
                return Array.Empty<CombatUnit>();
            var unit = FindAtSlot(allUnits, targetSlot, caster.Team);
            return unit != null && unit.IsAlive ? new[] { unit } : Array.Empty<CombatUnit>();
        }

        static IReadOnlyList<CombatUnit> ByRow(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits, int targetSlot)
        {
            if (!FormationGrid.IsValidSlot(targetSlot))
                return Array.Empty<CombatUnit>();
            int row = FormationGrid.RowOf(targetSlot);
            var result = new List<CombatUnit>();
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit != null && unit.IsAlive && unit.Team != caster.Team && FormationGrid.RowOf(unit.Slot) == row)
                    result.Add(unit);
            }
            return result;
        }

        static IReadOnlyList<CombatUnit> ByColumn(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits, int targetSlot)
        {
            if (!FormationGrid.IsValidSlot(targetSlot))
                return Array.Empty<CombatUnit>();
            int column = FormationGrid.ColumnOf(targetSlot);
            var result = new List<CombatUnit>();
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit != null && unit.IsAlive && unit.Team != caster.Team && FormationGrid.ColumnOf(unit.Slot) == column)
                    result.Add(unit);
            }
            return result;
        }

        static IReadOnlyList<CombatUnit> AdjacentEnemies(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits, int targetSlot)
        {
            if (!FormationGrid.IsValidSlot(targetSlot))
                return Array.Empty<CombatUnit>();

            var result = new List<CombatUnit>();
            var center = FindAtSlot(allUnits, targetSlot, EnemyTeam(caster));
            if (center == null || !center.IsAlive)
                return result;

            result.Add(center);
            var adjacent = FormationGrid.AdjacentSlots(targetSlot);
            for (int i = 0; i < adjacent.Count; i++)
            {
                var unit = FindAtSlot(allUnits, adjacent[i], EnemyTeam(caster));
                if (unit != null && unit.IsAlive)
                    result.Add(unit);
            }
            return result;
        }

        static IReadOnlyList<CombatUnit> AliveEnemies(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits)
        {
            var result = new List<CombatUnit>();
            var enemy = EnemyTeam(caster);
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit != null && unit.IsAlive && unit.Team == enemy)
                    result.Add(unit);
            }
            return result;
        }

        static IReadOnlyList<CombatUnit> AliveAllies(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits)
        {
            var result = new List<CombatUnit>();
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit != null && unit.IsAlive && unit.Team == caster.Team)
                    result.Add(unit);
            }
            return result;
        }

        static IReadOnlyList<CombatUnit> LowestHealth(CombatUnit caster, IReadOnlyList<CombatUnit> allUnits, bool enemiesOnly)
        {
            CombatUnit best = null;
            var targetTeam = enemiesOnly ? EnemyTeam(caster) : caster.Team;
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit == null || !unit.IsAlive || unit.Team != targetTeam)
                    continue;
                if (best == null
                    || unit.CurrentHealth < best.CurrentHealth
                    || (unit.CurrentHealth == best.CurrentHealth && unit.Slot < best.Slot))
                {
                    best = unit;
                }
            }
            return best != null ? new[] { best } : Array.Empty<CombatUnit>();
        }

        static CombatUnit FindAtSlot(IReadOnlyList<CombatUnit> allUnits, int slot, CombatTeam team)
        {
            for (int i = 0; i < allUnits.Count; i++)
            {
                var unit = allUnits[i];
                if (unit != null && unit.Slot == slot && unit.Team == team)
                    return unit;
            }
            return null;
        }

        static CombatTeam EnemyTeam(CombatUnit caster)
        {
            return caster.Team == CombatTeam.Hero ? CombatTeam.Enemy : CombatTeam.Hero;
        }
    }
}
