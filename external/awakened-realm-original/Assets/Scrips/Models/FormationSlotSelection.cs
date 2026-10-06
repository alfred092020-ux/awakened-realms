using System;
using AwakenedRealm.Scriptables;

namespace AwakenedRealm.Models
{
    [Serializable]
    public sealed class FormationSlotSelection
    {
        public const int GridSize = 9;
        public const int MaxPartySize = 5;

        public HeroSO Hero;
        public int SlotIndex;

        public FormationSlotSelection(HeroSO hero, int slotIndex)
        {
            Hero = hero;
            SlotIndex = slotIndex;
        }

        public bool IsValid => Hero != null && SlotIndex >= 0 && SlotIndex < GridSize;
    }
}
