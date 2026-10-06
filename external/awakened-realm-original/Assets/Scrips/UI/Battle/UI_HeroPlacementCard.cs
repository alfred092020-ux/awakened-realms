using System;
using AwakenedRealm.Enums;
using AwakenedRealm.Models;
using AwakenedRealm.Scriptables;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_HeroPlacementCard : MonoBehaviour
    {
        [SerializeField] TMP_Text _heroNameText;
        [SerializeField] TMP_Text _heroLevelText;
        [SerializeField] Image _heroImg;  // will be used later in the cards polish milestones
        [SerializeField] Button _btn;

        HeroSO _heroSO;
        public HeroSO GetHeroSO() => _heroSO;


        public Action<UI_HeroPlacementCard, Dragging> OnDrag;


        public void SetUI_HeroCard(HeroSO heroSO)
        {
            _heroSO = heroSO;
            _heroNameText.text = heroSO.GetHeroProfile().HeroName;
            _heroLevelText.text = heroSO.GetHeroProfile().HeroLevel.ToString();

            // we can use the 
            _heroImg.sprite = heroSO.GetHeroSprite();

        }

        public void OnDragStarted()
        {
            Debug.Log($"Hero Drag started");
            OnDrag?.Invoke(this, Dragging.started);
        }

        public void OnDragReleased()
        {
            Debug.Log($"Hero Drag released");
            OnDrag?.Invoke(this, Dragging.released);
        }
    }

}