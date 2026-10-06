using AwakenedRealm.Data;
using AwakenedRealm.UI;
using Cysharp.Threading.Tasks;
using UnityEngine;

namespace AwakenedRealm
{
    public class MainMenuUIManager : MonoBehaviour
    {
        public static MainMenuUIManager Instance;


        // References
        [SerializeField] UI_Profile _profileUI;
        [SerializeField] UI_MainMenuBottom _mainMenuBottomUI;

        private void Awake()
        {
            Instance = this;
        }


        async void OnEnable()
        {
            await UniTask.WaitUntil(() => ReusableData.Instance != null && ReusableUI.Instance != null);

            // since is already fetched from the auth screen, make sure onEnable we turn off the loading and other UI screens
            DisableAllUIScreens();
            FillProfile();
            SetupMainMenuBottom();

        }


        /// <summary>
        /// Fills the profile including all the profile related stats and information
        /// </summary>
        void FillProfile()
        {
            var data = ReusableData.Instance.GetPlayerProfileSO().GetPlayerData();
            _profileUI.SetUI_Profile(data.Profile);
            _profileUI.SetUI_Wallet(data.Wallet);
        }

        /// <summary>
        /// All the button callbacks and bottom main menu stuff
        /// </summary>
        void SetupMainMenuBottom()
        {
            _mainMenuBottomUI.SetUI_MainMenuBottom();
        }


        /// <summary>
        /// Disabling all UI screens at start for smooth start and to avoid any UI being left turned on from the auth screen accidentally
        /// </summary>
        void DisableAllUIScreens()
        {
            ReusableUI.Instance.DisableAllUIScreens();
        }
    }

}
