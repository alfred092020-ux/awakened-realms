using System;

namespace AwakenedRealm.EquipmentV2
{
    /// <summary>
    /// Deterministic enhancement rules: centralized rarity caps, monotonically
    /// increasing costs, no randomness, no failure, no destruction.
    /// </summary>
    public static class EnhancementRules
    {
        // Centralized caps by rarity.
        public const int MaxRare = 10;
        public const int MaxEpic = 15;
        public const int MaxLegendary = 20;
        public const int MaxMythic = 25;

        // Cost tuning knobs: gold and stones scale linearly with the target level.
        // Rebalance here only; costs stay strictly monotonic per rarity.
        static readonly int[] GoldPerLevel = { 120, 320, 780, 1600 };   // Rare..Mythic
        static readonly int[] StonesPerLevel = { 1, 2, 4, 7 };          // Rare..Mythic

        // Fraction of base stats gained per enhancement level (e.g. +8%/level).
        public const float EnhancementStatScalePerLevel = 0.08f;

        public static int MaxEnhancement(EquipmentRarity rarity)
        {
            switch (rarity)
            {
                case EquipmentRarity.Rare: return MaxRare;
                case EquipmentRarity.Epic: return MaxEpic;
                case EquipmentRarity.Legendary: return MaxLegendary;
                case EquipmentRarity.Mythic: return MaxMythic;
                default: throw new ArgumentOutOfRangeException(nameof(rarity), rarity, "Unknown rarity.");
            }
        }

        /// <summary>Cost to go from (nextLevel - 1) to nextLevel. nextLevel is 1-based.</summary>
        public static void CostForLevel(EquipmentRarity rarity, int nextLevel, out long gold, out int stones)
        {
            int idx = (int)rarity;
            if (idx < 0 || idx >= GoldPerLevel.Length)
                throw new ArgumentOutOfRangeException(nameof(rarity), rarity, "Unknown rarity.");
            if (nextLevel < 1 || nextLevel > MaxEnhancement(rarity))
                throw new ArgumentOutOfRangeException(nameof(nextLevel), nextLevel, "Level outside enhancement range.");

            gold = (long)GoldPerLevel[idx] * nextLevel;
            stones = StonesPerLevel[idx] * nextLevel;
        }

        /// <summary>
        /// Atomically enhances the instance one level: validates cap, then spends
        /// from the wallet; on insufficient resources nothing is deducted and the
        /// level is unchanged.
        /// </summary>
        public static bool TryEnhance(EquipmentInstance instance, EquipmentDefinition definition, EquipmentWallet wallet)
        {
            if (instance == null) throw new ArgumentNullException(nameof(instance));
            if (definition == null) throw new ArgumentNullException(nameof(definition));
            if (wallet == null) throw new ArgumentNullException(nameof(wallet));
            if (!string.Equals(instance.DefinitionId, definition.DefinitionId, StringComparison.Ordinal))
                return false;
            if (instance.EnhancementLevel >= MaxEnhancement(definition.Rarity))
                return false;

            long gold;
            int stones;
            CostForLevel(definition.Rarity, instance.EnhancementLevel + 1, out gold, out stones);

            if (!wallet.TrySpend(gold, stones))
                return false; // atomic: wallet untouched on failure

            instance.EnhancementLevel++;
            return true;
        }

        /// <summary>Multiplier applied to a definition's base stats at a given enhancement level.</summary>
        public static float EnhancementMultiplier(int enhancementLevel)
        {
            return 1f + EnhancementStatScalePerLevel * Math.Max(0, enhancementLevel);
        }
    }
}
