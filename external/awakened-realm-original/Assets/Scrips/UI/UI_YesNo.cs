using System;
using AwakenedRealm.Enums;
using AwakenedRealm.Models;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_YesNo : MonoBehaviour
    {
        [SerializeField] Button _yesBtn;
        [SerializeField] Button _noBtn;

        [SerializeField] TMP_Text _msgText;

        [SerializeField] Image _backgroundImg;

        [SerializeField] UI_Slide _slideUI;


        public void SetUI_YesNo(Action yesCallback, Action noCallback, string msg)
        {
            _yesBtn.onClick.RemoveAllListeners();
            _noBtn.onClick.RemoveAllListeners();

            Utils.FadeBackground(0.75f, 0.0f, _backgroundImg);
            _slideUI.Execute();


            _msgText.text = msg;


            _yesBtn.onClick.AddListener(() => { DisableUI(); yesCallback?.Invoke(); Utils.FadeBackground(0.0f, 0.0f, _backgroundImg); });
            _noBtn.onClick.AddListener(() => { DisableUI(); noCallback?.Invoke(); Utils.FadeBackground(0.0f, 0.0f, _backgroundImg); });
        }


        public void DisableUI()
        {
            Utils.FadeBackground(0.0f, 0.0f, _backgroundImg);
            _slideUI.Undo();
        }

    }

}