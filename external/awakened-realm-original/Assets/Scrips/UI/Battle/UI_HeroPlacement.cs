using System;
using System.Collections.Generic;
using AwakenedRealm.Models;
using AwakenedRealm.Enums;
using AwakenedRealm.Scriptables;
using CraftSome.CrossTouch;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_HeroPlacement : MonoBehaviour
    {
        [SerializeField] UI_HeroPlacementCard _heroCardPrefab;
        [SerializeField] Transform _heroCardParentTransform;
        [SerializeField] UI_BattlePlacementGrid _battlePlacementGridUI;
        public UI_BattlePlacementGrid GetBattlePlacementGridUI() => _battlePlacementGridUI;

        [SerializeField] UI_HeroPlacementCard _heroGhostCard;
        bool _isGhostingActive;

        readonly List<UI_HeroPlacementCard> _spawnedHeroCards = new List<UI_HeroPlacementCard>();

        [SerializeField] float _snapDistance = 6.0f;
        [SerializeField] UI_Button _startBattleBtn;
        [SerializeField] UI_Slide _slideUI;

        public Action<List<FormationSlotSelection>> OnStartBattle;

        public void SetUI_HeroPlacement(HeroSO[] heroesSO)
        {
            ClearHeroCards();
            if (heroesSO == null) return;

            foreach (var heroSO in heroesSO)
            {
                if (heroSO == null) continue;
                var newHeroCard = Instantiate(_heroCardPrefab, _heroCardParentTransform);
                newHeroCard.SetUI_HeroCard(heroSO);
                _spawnedHeroCards.Add(newHeroCard);
                newHeroCard.OnDrag += HandleOnDrag;
            }
        }

        public void DisableUI() => _slideUI.Undo();
        public void EnableUI() => _slideUI.Execute();

        void Start()
        {
            _startBattleBtn.OnClick.RemoveAllListeners();
            _startBattleBtn.OnClick.AddListener(HandleStartBattleClick);
        }

        void OnDisable()
        {
            ClearHeroCards();
        }

        void ClearHeroCards()
        {
            foreach (var heroCard in _spawnedHeroCards)
            {
                if (heroCard == null) continue;
                heroCard.OnDrag -= HandleOnDrag;
                Destroy(heroCard.gameObject);
            }
            _spawnedHeroCards.Clear();
        }

        void Update()
        {
            if (!_isGhostingActive || _heroGhostCard == null) return;

            Vector2 currentPosition = Input.mousePosition;
            if (Input.touchCount > 0) currentPosition = Input.GetTouch(0).position;
            _heroGhostCard.transform.position = currentPosition;
        }

        private void HandleStartBattleClick(MainMenuButtonType btnType)
        {
            var formation = _battlePlacementGridUI.GetFormation();
            if (!_battlePlacementGridUI.HasValidFormation())
            {
                var confirmUI = ReusableUI.Instance.GetConfirmUI();
                confirmUI.SetUI_Confirm(
                    $"Choose exactly {FormationSlotSelection.MaxPartySize} unique heroes. You currently have {formation.Count}.",
                    () => { });
                return;
            }

            var yesNoUI = ReusableUI.Instance.GetYesNoUI();
            yesNoUI.SetUI_YesNo(
                () => OnStartBattle?.Invoke(formation),
                () => { },
                "Formation ready. Start the battle?");
        }

        private void HandleOnDrag(UI_HeroPlacementCard card, Dragging dragging)
        {
            _isGhostingActive = dragging == Dragging.started;

            if (_heroGhostCard != null)
            {
                _heroGhostCard.gameObject.SetActive(_isGhostingActive);
                if (_isGhostingActive) _heroGhostCard.SetUI_HeroCard(card.GetHeroSO());
            }

            if (dragging == Dragging.started) return;

            var placementGridBlock = RaycastToUIBattlePlacementGridBlock();
            if (placementGridBlock == null) return;

            if (!_battlePlacementGridUI.TryPlaceHero(card.GetHeroSO(), placementGridBlock))
            {
                var confirmUI = ReusableUI.Instance.GetConfirmUI();
                confirmUI.SetUI_Confirm(
                    $"Your active formation is limited to {FormationSlotSelection.MaxPartySize} heroes.",
                    () => { });
            }
        }

        public UI_BattlePlacementGridBlock GetClosestGridToGhostCard(UI_BattlePlacementGridBlock[] placementGrids)
        {
            if (placementGrids == null || placementGrids.Length == 0 || _heroGhostCard == null) return null;

            UI_BattlePlacementGridBlock closestGrid = null;
            float closestDistance = float.MaxValue;
            Vector3 ghostCardPosition = _heroGhostCard.transform.position;

            foreach (var gridBlock in placementGrids)
            {
                if (gridBlock == null) continue;
                float distance = Vector3.Distance(gridBlock.transform.position, ghostCardPosition);
                if (distance < closestDistance)
                {
                    closestDistance = distance;
                    closestGrid = gridBlock;
                }
            }

            if (closestGrid != null && closestDistance <= _snapDistance)
            {
                _heroGhostCard.transform.position = closestGrid.transform.position;
                return closestGrid;
            }

            return null;
        }

        public UI_BattlePlacementGridBlock RaycastToUIBattlePlacementGridBlock()
        {
            Vector2 pointerPosition = Input.mousePosition;
            if (Input.touchCount > 0) pointerPosition = Input.GetTouch(0).position;

            var eventSystem = EventSystem.current;
            if (eventSystem == null) return null;

            var graphicRaycaster = GetComponentInParent<Canvas>()?.GetComponent<GraphicRaycaster>();
            if (graphicRaycaster == null) return null;

            var pointerEventData = new PointerEventData(eventSystem) { position = pointerPosition };
            var results = new List<RaycastResult>();
            graphicRaycaster.Raycast(pointerEventData, results);

            foreach (var result in results)
            {
                var hitObject = result.gameObject.GetComponent<UI_BattlePlacementGridBlock>();
                if (hitObject != null) return hitObject;
            }

            return null;
        }
    }
}
