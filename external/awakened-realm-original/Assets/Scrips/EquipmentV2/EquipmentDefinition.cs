using System;
using System.Collections.Generic;

namespace AwakenedRealm.EquipmentV2
{
    [Serializable]
    public sealed class EquipmentDefinition
    {
        public string DefinitionId;
        public string DisplayName;
        public EquipmentSlot Slot;
        public EquipmentRarity Rarity;
        public int LevelRequirement;
        public string SetId;
        public List<StatModifier> BaseStats = new List<StatModifier>();

        public EquipmentDefinition() { }

        public EquipmentDefinition(
            string definitionId,
            string displayName,
            EquipmentSlot slot,
            EquipmentRarity rarity,
            int levelRequirement,
            string setId,
            params StatModifier[] baseStats)
        {
            if (string.IsNullOrWhiteSpace(definitionId))
                throw new ArgumentException("Definition ID is required.", nameof(definitionId));

            DefinitionId = definitionId;
            DisplayName = displayName ?? definitionId;
            Slot = slot;
            Rarity = rarity;
            LevelRequirement = Math.Max(1, levelRequirement);
            SetId = string.IsNullOrWhiteSpace(setId) ? null : setId;
            if (baseStats != null)
                BaseStats.AddRange(baseStats);
        }

        public float FlatStat(EquipmentStatType stat)
        {
            float total = 0f;
            for (int i = 0; i < BaseStats.Count; i++)
                if (BaseStats[i].Stat == stat)
                    total += BaseStats[i].Flat;
            return total;
        }

        public float PercentStat(EquipmentStatType stat)
        {
            float total = 0f;
            for (int i = 0; i < BaseStats.Count; i++)
                if (BaseStats[i].Stat == stat)
                    total += BaseStats[i].Percent;
            return total;
        }
    }
}
