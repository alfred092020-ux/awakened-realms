#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using AwakenedRealm.CombatV2;
using UnityEditor;
using UnityEngine;

public static class ValidateCombatV2
{
    [MenuItem("Awakened Realms/Validate CombatV2 Foundation")]
    public static void Run()
    {
        // Catalog integrity
        var report = CombatV2Validation.Run();
        Assert(report.Success, "Catalog: " + report.Summary() + " | " + string.Join("; ", report.Failures));
        Assert(report.HeroCount == 12, "Expected 12 heroes");
        Assert(report.AbilityCount == 48, "Expected 48 abilities (12x4)");

        // Representative targeting on a deterministic 3x3 board
        var units = new List<CombatUnit>
        {
            new CombatUnit("hero-dps",     slot: 0, currentHealth: 800, maxHealth: 1000, role: HeroRole.Dps,      team: CombatTeam.Hero),
            new CombatUnit("hero-support", slot: 3, currentHealth: 600, maxHealth: 1000, role: HeroRole.Support,  team: CombatTeam.Hero),
            new CombatUnit("hero-tank",    slot: 6, currentHealth: 900, maxHealth: 1000, role: HeroRole.Defender, team: CombatTeam.Hero),
            new CombatUnit("enemy-a",      slot: 0, currentHealth: 500, maxHealth: 1000, role: HeroRole.Dps,      team: CombatTeam.Enemy),
            new CombatUnit("enemy-b",      slot: 1, currentHealth: 700, maxHealth: 1000, role: HeroRole.Support,  team: CombatTeam.Enemy),
            new CombatUnit("enemy-c",      slot: 4, currentHealth: 300, maxHealth: 1000, role: HeroRole.Dps,      team: CombatTeam.Enemy),
            new CombatUnit("enemy-d",      slot: 7, currentHealth: 900, maxHealth: 1000, role: HeroRole.Defender, team: CombatTeam.Enemy)
        };

        var caster = units[0];

        // Single enemy
        var single = TargetResolver.Resolve(TargetPattern.SingleEnemy, caster, units, selectedTargetSlot: 4);
        Assert(single.Count == 1 && single[0].UnitId == "enemy-c", "SingleEnemy resolves chosen enemy slot");

        // Row enemies (row 1 on enemy side => enemy-c only)
        var row = TargetResolver.Resolve(TargetPattern.RowEnemies, caster, units, selectedTargetSlot: 4);
        Assert(row.Count == 1 && row[0].UnitId == "enemy-c", "RowEnemies resolves enemy row");

        // Column enemies (column 0 => enemy-a only)
        var column = TargetResolver.Resolve(TargetPattern.ColumnEnemies, caster, units, selectedTargetSlot: 0);
        Assert(column.Count == 1 && column[0].UnitId == "enemy-a", "ColumnEnemies resolves enemy column");

        // Adjacent enemies (center on slot 0 hits enemy-a + enemy-b + enemy-c)
        var adjacent = TargetResolver.Resolve(TargetPattern.AdjacentEnemies, caster, units, selectedTargetSlot: 0);
        Assert(adjacent.Count == 3, "AdjacentEnemies hits main + adjacent");

        // All enemies
        var allEnemies = TargetResolver.Resolve(TargetPattern.AllEnemies, caster, units);
        Assert(allEnemies.Count == 4, "AllEnemies hits all four enemies");

        // Lowest-HP enemy
        var lowestEnemy = TargetResolver.Resolve(TargetPattern.LowestHealthEnemy, caster, units);
        Assert(lowestEnemy.Count == 1 && lowestEnemy[0].UnitId == "enemy-c", "LowestHealthEnemy picks lowest current HP");

        // Lowest-HP ally
        var lowestAlly = TargetResolver.Resolve(TargetPattern.LowestHealthAlly, caster, units);
        Assert(lowestAlly.Count == 1 && lowestAlly[0].UnitId == "hero-support", "LowestHealthAlly picks lowest current HP ally");

        // Self
        var self = TargetResolver.Resolve(TargetPattern.Self, caster, units);
        Assert(self.Count == 1 && self[0].UnitId == caster.UnitId, "Self resolves caster");

        // All allies
        var allAllies = TargetResolver.Resolve(TargetPattern.AllAllies, caster, units);
        Assert(allAllies.Count == 3, "AllAllies hits all three heroes");

        // Slot validity and preferred protection target
        Assert(!TargetResolver.IsSelectableEnemySlot(-1, units, CombatTeam.Hero), "Invalid slot rejected");
        Assert(!TargetResolver.IsSelectableEnemySlot(9, units, CombatTeam.Hero), "Out-of-range slot rejected");
        Assert(TargetResolver.IsSelectableEnemySlot(4, units, CombatTeam.Hero), "Occupied enemy slot accepted");
        Assert(!TargetResolver.IsSelectableEnemySlot(2, units, CombatTeam.Hero), "Empty enemy slot rejected");

        var protection = TargetResolver.PreferredProtectionTarget(units, CombatTeam.Hero);
        Assert(protection != null && protection.UnitId == "hero-tank", "Defender preferred as protection target");

        // Positional damage multipliers
        Assert(Mathf.Approximately(FormationGrid.IncomingDamageMultiplier(0), 1.00f), "Front row takes 100%");
        Assert(Mathf.Approximately(FormationGrid.IncomingDamageMultiplier(8), 0.60f), "Back row takes 60%");

        Debug.Log("AWAKENED_REALMS_COMBAT_V2_PASS | " + report.Summary());
    }

    static void Assert(bool condition, string label)
    {
        if (!condition)
            throw new InvalidOperationException("CombatV2 validation failed: " + label);
    }
}
#endif
