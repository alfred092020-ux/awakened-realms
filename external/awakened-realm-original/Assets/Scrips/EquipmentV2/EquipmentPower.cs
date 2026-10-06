using System;

namespace AwakenedRealm.EquipmentV2
{
    /// <summary>
    /// Deterministic equipment power score. Centralized coefficients make
    /// rebalancing a single-file change; enhancement adds a per-level bonus.
    /// </summary>
    public static class EquipmentPower
    {
        // Rebalance knobs: weight per stat point (flat stats) and per 1.0 of a
        // percent modifier. Percent weights are per unit (0.10 = 10%).
        public const float WeightHP = 0.10f;
        public const float WeightATK = 1.0f;
        public const float WeightDEF = 0.9f;
        public const float WeightMAG = 1.0f;
        public const float WeightSPD = 2.0f;
        public const float WeightCritRate = 400f;   // per 1.0 (so 10% -> 40)
        public const float WeightResistance = 300f; // per 1.0

        /// <summary>Extra score per enhancement level, relative to base score (e.g. 0.06 = +6%/level).</summary>
        public const float EnhancementLevelBonus = 0.06f;

        static float StatWeight(EquipmentStatType stat)
        {
            switch (stat)
            {
                case EquipmentStatType.HP: return WeightHP;
                case EquipmentStatType.ATK: return WeightATK;
                case EquipmentStatType.DEF: return WeightDEF;
                case EquipmentStatType.MAG: return WeightMAG;
                case EquipmentStatType.SPD: return WeightSPD;
                case EquipmentStatType.CritRate: return WeightCritRate;
                case EquipmentStatType.Resistance: return WeightResistance;
                default: throw new ArgumentOutOfRangeException(nameof(stat), stat, "Unknown stat.");
            }
        }

        /// <summary>Base (level 0) power of a definition.</summary>
        public static float BasePower(EquipmentDefinition definition)
        {
            if (definition == null)
                return 0f;
            float score = 0f;
            for (int i = 0; i < definition.BaseStats.Count; i++)
            {
                StatModifier mod = definition.BaseStats[i];
                score += mod.Flat * StatWeight(mod.Stat);
                score += mod.Percent * StatWeight(mod.Stat) * 100f; // percent valued vs a nominal 100-stat scale
            }
            return score;
        }

        /// <summary>Deterministic contribution score for a single instance.</summary>
        public static float InstancePower(EquipmentInstance instance, EquipmentDefinition definition)
        {
            if (instance == null || definition == null)
                return 0f;
            float baseScore = BasePower(definition);
            return baseScore * (1f + EnhancementLevelBonus * Math.Max(0, instance.EnhancementLevel));
        }

        /// <summary>Total equipment power of a hero's equipped loadout.</summary>
        public static float LoadoutPower(string heroId, EquipmentLoadouts loadouts, EquipmentInventory inventory, EquipmentCatalog catalog)
        {
            float total = 0f;
            if (loadouts == null || inventory == null || catalog == null)
                return total;

            var equipped = loadouts.EquippedInstances(heroId);
            for (int i = 0; i < equipped.Count; i++)
            {
                EquipmentInstance instance = inventory.Find(equipped[i]);
                if (instance == null)
                    continue;
                EquipmentDefinition def = catalog.Find(instance.DefinitionId);
                total += InstancePower(instance, def);
            }
            return total;
        }
    }
}
