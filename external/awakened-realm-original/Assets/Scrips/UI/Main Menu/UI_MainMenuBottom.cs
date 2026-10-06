using System;
using AwakenedRealm.Enums;
using UnityEngine;

namespace AwakenedRealm.UI
{
    public class UI_MainMenuBottom : MonoBehaviour
    {
        [SerializeField] UI_Button[] _btns;

        [SerializeField] UI_Slide _slideUI;

        bool _navigatingAway;

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
                // Latch so rapid re-taps cannot enqueue duplicate scene loads.
                if (_navigatingAway) return;

                if (!Application.CanStreamedLevelBeLoaded("Battle"))
                {
                    Debug.LogWarning("[MainMenuBottom] Battle scene is not in Build Settings; staying on MainMenu.");
                    return;
                }

                _navigatingAway = true;
                // just the load the scene for now
                UnityEngine.SceneManagement.SceneManager.LoadScene("Battle");
            }
        }


        #endregion
    }

}
