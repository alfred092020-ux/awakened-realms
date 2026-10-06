using System;
using AwakenedRealm.Enums;
using UnityEngine;

namespace AwakenedRealm.UI
{
    public class UI_MainMenuBottom : MonoBehaviour
    {
        [SerializeField] UI_Button[] _btns;

        [SerializeField] UI_Slide _slideUI;

        void Start()
        {
            _slideUI.Execute();
        }


        public void SetUI_MainMenuBottom()
        {
            foreach (var btn in _btns) btn.OnClick.AddListener(HandleBtnClick);
        }

        void OnDisable()
        {
            foreach (var btn in _btns) btn.OnClick.RemoveListener(HandleBtnClick);
        }

        #region Listeners


        private void HandleBtnClick(MainMenuButtonType btnType)
        {
            if (btnType == MainMenuButtonType.battle)
            {
                // just the load the scene for now
                UnityEngine.SceneManagement.SceneManager.LoadScene("Battle");
            }
        }


        #endregion
    }

}