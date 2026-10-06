using System.Collections.Generic;
using System.Linq;
using AwakenedRealm.Models;
using AwakenedRealm.Scriptables;
using UnityEngine;

namespace AwakenedRealm.UI
{
    public class UI_BattlePlacementGrid : MonoBehaviour
    {
        [SerializeField] UI_BattlePlacementGridBlock[] _gridBlocksUI;
        public UI_BattlePlacementGridBlock[] GetGridBlocksUI() => _gridBlocksUI;

        public int OccupiedCount => _gridBlocksUI == null ? 0 : _gridBlocksUI.Count(x => x != null && x.isGridBlockTaken && x.GetHeroSO() != null);

        public bool TryPlaceHero(HeroSO heroSO, UI_BattlePlacementGridBlock selectedBlock)
        {
            if (heroSO == null || selectedBlock == null || _gridBlocksUI == null || !_gridBlocksUI.Contains(selectedBlock))
                return false;

            var currentBlock = _gridBlocksUI.FirstOrDefault(x => x != null && x.GetHeroSO() == heroSO);
            bool isMove = currentBlock != null && currentBlock != selectedBlock;

            if (!selectedBlock.isGridBlockTaken && currentBlock == null && OccupiedCount >= FormationSlotSelection.MaxPartySize)
                return false;

            if (isMove) currentBlock.ClearHero();
            selectedBlock.SetHeroImage(heroSO);
            return true;
        }

        public void SetHeroForGridBlock(HeroSO heroSO, UI_BattlePlacementGridBlock selectedBlock)
        {
            TryPlaceHero(heroSO, selectedBlock);
        }

        public void ClearGridBlock(UI_BattlePlacementGridBlock block)
        {
            if (block == null || _gridBlocksUI == null || !_gridBlocksUI.Contains(block)) return;
            block.ClearHero();
        }

        public List<FormationSlotSelection> GetFormation()
        {
            if (_gridBlocksUI == null) return new List<FormationSlotSelection>();

            return _gridBlocksUI
                .Where(x => x != null && x.isGridBlockTaken && x.GetHeroSO() != null)
                .Select(x => new FormationSlotSelection(x.GetHeroSO(), x.SlotIndex))
                .Where(x => x.IsValid)
                .OrderBy(x => x.SlotIndex)
                .Take(FormationSlotSelection.MaxPartySize)
                .ToList();
        }

        public bool HasValidFormation()
        {
            var formation = GetFormation();
            return formation.Count == FormationSlotSelection.MaxPartySize
                && formation.Select(x => x.SlotIndex).Distinct().Count() == formation.Count
                && formation.Select(x => x.Hero).Distinct().Count() == formation.Count;
        }
    }
}
