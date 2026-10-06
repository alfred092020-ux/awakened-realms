using System;

namespace AwakenedRealm.EquipmentV2
{
    public enum EquipmentSlot
    {
        Weapon,
        Helmet,
        Armor,
        Boots,
        Accessory,
        Relic
    }

    // Kept separate from AwakenedRealm.Enums.HeroRarity to avoid serialization coupling.
    public enum EquipmentRarity
    {
        Rare,
        Epic,
        Legendary,
        Mythic
    }

    public enum EquipmentStatType
    {
        HP,
        ATK,
        DEF,
        MAG,
        SPD,
        CritRate,
        Resistance
    }

    [Serializable]
    public struct StatModifier
    {
        public EquipmentStatType Stat;
        public float Flat;
        public float Percent;

        public StatModifier(EquipmentStatType stat, float flat, float percent)
        {
            Stat = stat;
            Flat = flat;
            Percent = percent;
        }

        public static StatModifier FlatOf(EquipmentStatType stat, float flat)
        {
            return new StatModifier(stat, flat, 0f);
        }

        public static StatModifier PercentOf(EquipmentStatType stat, float percent)
        {
            return new StatModifier(stat, 0f, percent);
        }
    }
}
