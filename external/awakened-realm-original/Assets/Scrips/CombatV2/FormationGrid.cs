using System;
using System.Collections.Generic;

namespace AwakenedRealm.CombatV2
{
    /// <summary>
    /// One combat unit placed on the 3x3 formation grid. Slot index is
    /// 0..8; row 0 is the front row, row 2 is the back row.
    /// </summary>
    public sealed class CombatUnit
    {
        public readonly string UnitId;
        public readonly int Slot;
        public readonly int CurrentHealth;
        public readonly int MaxHealth;
        public readonly HeroRole Role;
        public readonly CombatTeam Team;

        public CombatUnit(string unitId, int slot, int currentHealth, int maxHealth, HeroRole role, CombatTeam team)
        {
            if (string.IsNullOrWhiteSpace(unitId))
                throw new ArgumentException("Unit id is required.", nameof(unitId));
            if (slot < 0 || slot >= FormationGrid.SlotCount)
                throw new ArgumentOutOfRangeException(nameof(slot), "Slot must be 0..8.");
            if (maxHealth <= 0)
                throw new ArgumentOutOfRangeException(nameof(maxHealth), "Max health must be positive.");
            if (currentHealth < 0 || currentHealth > maxHealth)
                throw new ArgumentOutOfRangeException(nameof(currentHealth), "Current health must be within 0..maxHealth.");

            UnitId = unitId;
            Slot = slot;
            CurrentHealth = currentHealth;
            MaxHealth = maxHealth;
            Role = role;
            Team = team;
        }

        public bool IsAlive => CurrentHealth > 0;

        public float HealthPercent => (float)CurrentHealth / MaxHealth;
    }

    /// <summary>
    /// Team side of a combat unit. Deliberately mirrors the existing
    /// AwakenedRealm.Teams enum shape without depending on it.
    /// </summary>
    public enum CombatTeam
    {
        Hero,
        Enemy
    }

    /// <summary>
    /// Pure, deterministic geometry for the stable 3x3 formation grid.
    /// Slot indices are row-major: 0..2 front row, 3..5 middle row,
    /// 6..8 back row. Columns are left-to-right 0..2.
    /// </summary>
    public static class FormationGrid
    {
        public const int Rows = 3;
        public const int Columns = 3;
        public const int SlotCount = Rows * Columns;

        /// <summary>Front row receives this fraction of direct damage.</summary>
        public const float FrontRowIncomingDamageMultiplier = 1.00f;

        /// <summary>Back row receives this fraction of direct damage.</summary>
        public const float BackRowIncomingDamageMultiplier = 0.60f;

        public static int RowOf(int slot)
        {
            ValidateSlot(slot);
            return slot / Columns;
        }

        public static int ColumnOf(int slot)
        {
            ValidateSlot(slot);
            return slot % Columns;
        }

        public static int SlotOf(int row, int column)
        {
            if (row < 0 || row >= Rows)
                throw new ArgumentOutOfRangeException(nameof(row));
            if (column < 0 || column >= Columns)
                throw new ArgumentOutOfRangeException(nameof(column));
            return row * Columns + column;
        }

        public static bool IsFrontRow(int slot)
        {
            return RowOf(slot) == 0;
        }

        public static bool IsBackRow(int slot)
        {
            return RowOf(slot) == Rows - 1;
        }

        /// <summary>
        /// Row indices: 0 = front, 1 = middle, 2 = back.
        /// </summary>
        public static IReadOnlyList<int> RowSlots(int row)
        {
            if (row < 0 || row >= Rows)
                throw new ArgumentOutOfRangeException(nameof(row));
            return new[] { row * Columns, row * Columns + 1, row * Columns + 2 };
        }

        /// <summary>
        /// Column indices: 0 = left, 1 = center, 2 = right.
        /// </summary>
        public static IReadOnlyList<int> ColumnSlots(int column)
        {
            if (column < 0 || column >= Columns)
                throw new ArgumentOutOfRangeException(nameof(column));
            return new[] { column, column + Columns, column + Columns * 2 };
        }

        /// <summary>
        /// All eight surrounding slots (orthogonal + diagonal) in stable
        /// row-major order. Excludes the center slot itself.
        /// </summary>
        public static IReadOnlyList<int> AdjacentSlots(int slot)
        {
            ValidateSlot(slot);
            int row = RowOf(slot);
            int column = ColumnOf(slot);
            var result = new List<int>(8);
            for (int dr = -1; dr <= 1; dr++)
            {
                for (int dc = -1; dc <= 1; dc++)
                {
                    if (dr == 0 && dc == 0)
                        continue;
                    int r = row + dr;
                    int c = column + dc;
                    if (r >= 0 && r < Rows && c >= 0 && c < Columns)
                        result.Add(SlotOf(r, c));
                }
            }
            return result;
        }

        /// <summary>
        /// Incoming direct-damage multiplier for a unit at the given slot.
        /// Front row is fully exposed; back row is shielded by formation.
        /// Middle row currently uses the front-row multiplier to keep the
        /// default simple and tunable.
        /// </summary>
        public static float IncomingDamageMultiplier(int slot)
        {
            return IsBackRow(slot) ? BackRowIncomingDamageMultiplier : FrontRowIncomingDamageMultiplier;
        }

        public static bool IsValidSlot(int slot)
        {
            return slot >= 0 && slot < SlotCount;
        }

        static void ValidateSlot(int slot)
        {
            if (!IsValidSlot(slot))
                throw new ArgumentOutOfRangeException(nameof(slot), "Slot must be 0..8.");
        }
    }
}
