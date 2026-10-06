using System;
using AwakenedRealm.Models;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_Confirm : MonoBehaviour
    {
        [SerializeField] private UI_Slide _slideUI;
        [SerializeField] private TMP_Text _confirmText;
        [SerializeField] private Image _backgroundImg;
        [SerializeField] private Button _confirmBtn;

        [SerializeField] private bool _undoOnStart;

        private void Start()
        {
            if (_undoOnStart)
            {
                _confirmText.text = "";
                _slideUI.Undo();
                Utils.FadeBackground(0.0f, 0.0f, _backgroundImg);
            }
        }


        public void SetUI_Confirm(string msg, Action onConfirm)
        {
            _confirmText.text = msg;
            _slideUI.Execute();
            Utils.FadeBackground(0.75f, 0.0f, _backgroundImg);
            _backgroundImg.raycastTarget = true;

            _confirmBtn.onClick.RemoveAllListeners();
            _confirmBtn.onClick.AddListener(() =>
            {
                Utils.FadeBackground(0.0f, 0.0f, _backgroundImg);
                _backgroundImg.raycastTarget = false;
                onConfirm?.Invoke();
                _slideUI.Undo();
            });
        }

        public void DisableScreen()
        {
            _slideUI.Undo();
        }
    }
}