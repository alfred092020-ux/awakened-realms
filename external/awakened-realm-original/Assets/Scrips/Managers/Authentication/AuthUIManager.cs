using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using AwakenedRealm.Data;
using AwakenedRealm.Keys;
using AwakenedRealm.Models;
using AwakenedRealm.Services;
using AwakenedRealm.Services.Authentication;
using AwakenedRealm.UI;
using Cysharp.Threading.Tasks;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AwakenedRealm
{
    public class AuthUIManager : MonoBehaviour
    {
        public static AuthUIManager Instance;

        [SerializeField] UI_Signup _signupUI;
        [SerializeField] UI_Signin _signinUI;

        [Tooltip("The short delay when switching from signup to signin and vice versa")]
        [SerializeField]
        private float _screenSwitchDelay = .5f;

        // Guards against double-submit / overlapping successful-auth pipelines.
        private bool _authContinuationInProgress;

        private void Awake()
        {
            Instance = this;
        }

        private void OnEnable()
        {
            _signinUI.OnSwitch.AddListener(HandleSigninSwitch);
            _signupUI.OnSwitch.AddListener(HandleSignupSwitch);

            _signinUI.OnSigninSuccess += HandleSigninSuccess;
        }



        private void OnDisable()
        {
            _signinUI.OnSwitch.RemoveListener(HandleSigninSwitch);
            _signupUI.OnSwitch.RemoveListener(HandleSignupSwitch);

            _signinUI.OnSigninSuccess -= HandleSigninSuccess;
        }

        #region Public auth entry points

        /// <summary>
        /// Kicks off a real PlayFab guest login (device-bound on Android).
        /// Wire this to a "Play as Guest" button. On success it flows through
        /// the exact same continuation as email sign-in.
        /// </summary>
        public void SignInAsGuest()
        {
            if (_authContinuationInProgress) return;

            var loadingUI = ReusableUI.Instance.GetLoadingUI();
            loadingUI?.SetUI_Text("Signing in as guest...");
            loadingUI?.SetUI_LoadingAnimation(true);

            GuestAuthService.SignInAsGuest(res => HandleProviderSigninResult(res));
        }

        /// <summary>
        /// Kicks off a real Google sign-in -> PlayFab login. If the Google
        /// provider or OAuth configuration is absent, the result fails closed
        /// with a machine-readable <see cref="AuthFailureKind"/> instead of a
        /// fabricated success.
        /// </summary>
        public void SignInWithGoogle()
        {
            if (_authContinuationInProgress) return;

            var loadingUI = ReusableUI.Instance.GetLoadingUI();
            loadingUI?.SetUI_Text("Signing in with Google...");
            loadingUI?.SetUI_LoadingAnimation(true);

            GoogleSignInService.SignInWithGoogle(res => HandleProviderSigninResult(res));
        }

        #endregion

        #region Provider result routing

        /// <summary>
        /// Shared entry for guest/Google sign-in results. Errors stay honest:
        /// no fallback into guest on a failed Google or email attempt.
        /// </summary>
        private async void HandleProviderSigninResult(SigninResult res)
        {
            var loadingUI = ReusableUI.Instance.GetLoadingUI();
            if (res == null || res.IsSuccess == false)
            {
                loadingUI?.SetUI_Text($"Couldn't sign you in, {res?.ErrorMsg}");
                loadingUI?.SetUI_LoadingAnimation(true);
                await UniTask.WaitForSeconds(3.0f);
                loadingUI?.SetUI_LoadingAnimation(false);
                Debug.Log($"Signin failed ({res?.Provider}, {res?.FailureKind}): {res?.ErrorMsg}");
                return;
            }

            loadingUI?.SetUI_Text($"Signed in, {res.DisplayName}");
            await UniTask.WaitForSeconds(1.0f);
            HandleSigninSuccess(res);
        }

        #endregion

        #region Listeners

        private async void HandleSignupSwitch()
        {
            Debug.Log($"Switch 1");
            // switching from signup to signin
            _signupUI.SetUI_Signup(false);
            await UniTask.WaitForSeconds(_screenSwitchDelay);
            _signinUI.SetUI_Signin(true);
        }

        private async void HandleSigninSwitch()
        {
            Debug.Log($"Switch 2");
            // switching from signin to signup
            _signinUI.SetUI_Signin(false);
            await UniTask.WaitForSeconds(_screenSwitchDelay);
            _signupUI.SetUI_Signup(true);
        }



        /// <summary>
        /// After successful signin
        /// </summary>
        private async void HandleSigninSuccess(SigninResult res)
        {
            if (_authContinuationInProgress)
            {
                Debug.LogWarning("Auth continuation already running; ignoring duplicate success.");
                return;
            }
            _authContinuationInProgress = true;

            var loadingUI = ReusableUI.Instance.GetLoadingUI();
            loadingUI?.SetUI_Text("Loading game...");
            loadingUI?.SetUI_LoadingAnimation(true);

            // before loading into the new scene, we need to check if there's some data exists so can populate it for the first time
            bool result = await InitializeHeroDataOnBackend();
            Debug.Log($"Initializing result is {result}");

            AsyncOperation operation = SceneManager.LoadSceneAsync(SceneKeys.MainMenuSceneKey);

            // here we need to check if it's first time sign in of the user, so if it is then we can upload the data temporarily for getting the user on board

            // If you want to show progress:
            while (!operation.isDone)
            {
                // NOTE: operation.progress goes 0..0.9 until it activates
                // you can map it if you have a progress bar
                // loadingUI?.SetProgress(operation.progress);

                await UniTask.Yield(PlayerLoopTiming.Update); // <-- this is the key
            }

            // Scene loaded
            loadingUI?.SetUI_LoadingAnimation(false);
        }
        #endregion


        async Task<bool> InitializeHeroDataOnBackend()
        {
            // initliaze the database, check if the data doesn't exist then populate it with HeroProfiles and PlayerData
            bool res = await PlayfabService.UserDataExists();

            if (res == false)
            {
                await PlayfabService.UpdatePlayerData(ReusableData.Instance.GetPlayerProfileSO().GetPlayerData());

                List<HeroProfile> heroProfilesList = new List<HeroProfile>();

                foreach (var heroSO in ReusableData.Instance.GetHeroSOCollection().GetAllHeroes()) heroProfilesList.Add(heroSO.GetHeroProfile());

                await PlayfabService.UpdateHeroProfile(heroProfilesList);

                Debug.Log($"Info uploaded");
                return true;
            }
            else
            {
                Debug.Log($"Info already exists");
                return false;
            }

        }




    }
}
