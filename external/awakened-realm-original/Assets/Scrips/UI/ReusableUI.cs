using System;
using UnityEngine;

namespace AwakenedRealm.UI
{
    public class ReusableUI : MonoBehaviour
    {
        public static ReusableUI Instance;

        [SerializeField] private UI_Loading _loadingUI;
        public UI_Loading GetLoadingUI() => _loadingUI;
        [SerializeField] UI_Confirm _confirmUI;
        public UI_Confirm GetConfirmUI() => _confirmUI;
        [SerializeField] UI_YesNo _yesNoUI;
        public UI_YesNo GetYesNoUI() => _yesNoUI;


        private void Awake()
        {
            if (Instance != null && Instance != this) Destroy(gameObject);
            else
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }

            DisableAllUIScreens();
        }


        public void DisableAllUIScreens()
        {
            _loadingUI.SetUI_LoadingAnimation(false);
            _confirmUI.DisableScreen();
            _yesNoUI.DisableUI();
        }
    }
}