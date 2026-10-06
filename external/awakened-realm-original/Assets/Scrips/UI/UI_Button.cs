using System;
using AwakenedRealm.Enums;
using Cysharp.Threading.Tasks;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;


namespace AwakenedRealm.UI
{

    [RequireComponent(typeof(UnityEngine.UI.Button))]
    public class UI_Button : MonoBehaviour
    {
        Button _btn;

        [SerializeField] UI_Scale _scaleUI;
        [SerializeField] MainMenuButtonType _btnType;

        public UnityEvent<MainMenuButtonType> OnClick;
        void OnEnable()
        {
            _btn = GetComponent<Button>();

            _btn.onClick.AddListener(HandleBtnClick);
        }

        void OnDisable()
        {
            _btn.onClick.RemoveAllListeners();
        }

        #region Listeners


        private async void HandleBtnClick()
        {
            _scaleUI.StartScaling();
            await UniTask.WaitForSeconds(1.5f);
            OnClick?.Invoke(_btnType);
            _scaleUI.StopScaling();
        }


        #endregion
    }

}