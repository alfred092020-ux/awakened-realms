using System;

namespace AwakenedRealm.EquipmentV2
{
    /// <summary>
    /// Player-owned currencies consumed by enhancement. Mutation is only via
    /// TrySpend so deductions stay atomic (all-or-nothing).
    /// </summary>
    [Serializable]
    public sealed class EquipmentWallet
    {
        public long Gold;
        public int EnhancementStones;

        public EquipmentWallet() { }

        public EquipmentWallet(long gold, int enhancementStones)
        {
            Gold = Math.Max(0, gold);
            EnhancementStones = Math.Max(0, enhancementStones);
        }

        public bool CanAfford(long gold, int stones)
        {
            return gold >= 0 && stones >= 0 && Gold >= gold && EnhancementStones >= stones;
        }

        public bool TrySpend(long gold, int stones)
        {
            if (!CanAfford(gold, stones))
                return false;

            Gold -= gold;
            EnhancementStones -= stones;
            return true;
        }
    }
}
