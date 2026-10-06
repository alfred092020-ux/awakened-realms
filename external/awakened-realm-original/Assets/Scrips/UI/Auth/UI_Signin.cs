using System;
using AwakenedRealm.Data;
using AwakenedRealm.Models;
using AwakenedRealm.Services;
using Cysharp.Threading.Tasks;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_Signin : MonoBehaviour
    {
        [SerializeField] private Button _signinBtn;
        [SerializeField] private Button _createAccountBtn;
        [SerializeField] private UI_Slide _slideUI;

        public Action<SigninResult> OnSigninSuccess;
        public Action OnSigninFailed;
        public UnityEvent OnSwitch;


        private string _email;
        private string _password;


        private void OnEnable()
        {
            _signinBtn.onClick.AddListener(HandleSignin);
            _createAccountBtn.onClick.AddListener(HandleCreateAccount);
            ResetFields();
        }

        private void OnDisable()
        {
            _signinBtn.onClick.RemoveListener(HandleSignin);
            _createAccountBtn.onClick.RemoveListener(HandleCreateAccount);
        }

        public void SetUI_Signin(bool isEnabled = false)
        {
            if (isEnabled) _slideUI.Execute();
            else _slideUI.Undo();
        }

        private (bool, string) AllFieldsAreOk()
        {
            if (_email != string.Empty && _password != string.Empty) return (true, "");
            return (false, "Make sure all fields are filled...");
        }

        private void ResetFields()
        {
            _email = _password = string.Empty;
        }

        #region Listeners

        /// <summary>
        /// Not creating account in a literal sense, just switching to signup tab/screen
        /// </summary>
        private void HandleCreateAccount()
        {
            OnSwitch?.Invoke();
        }

        private async void HandleSignin()
        {
            var loadingUI = ReusableUI.Instance?.GetLoadingUI();
            var confirmUI = ReusableUI.Instance?.GetConfirmUI();

            var (areFieldsGood, msg) = AllFieldsAreOk();
            Debug.Log($"All result {areFieldsGood}");
            if (areFieldsGood == false)
            {
                confirmUI.SetUI_Confirm(msg, () => { });
                return;
            }


            loadingUI?.SetUI_Text("Signing you in...");
            loadingUI?.SetUI_LoadingAnimation(true);

            // call the signin API
            PlayfabService.SignIn(new SigninRequest()
            {
                Email = _email,
                Password = _password
            }, async signinRes =>
            {
                if (signinRes.IsSuccess == false)
                {
                    // show error with UI

                    loadingUI?.SetUI_Text($"Couldn't sign you in, {signinRes.ErrorMsg}");
                    loadingUI?.SetUI_LoadingAnimation(true);
                    await UniTask.WaitForSeconds(3.0f);
                    loadingUI.SetUI_LoadingAnimation(false);
                    Debug.Log($"Signin failed, err: {signinRes.ErrorMsg}");
                    OnSigninFailed?.Invoke();
                    return;
                }

                loadingUI?.SetUI_Text($"Signed in, {signinRes.DisplayName}");
                loadingUI?.SetUI_LoadingAnimation(true);
                await UniTask.WaitForSeconds(3.0f);
                loadingUI.SetUI_LoadingAnimation(false);
                //Debug.Log($"Signed in successfully, displayName: {signinRes.DisplayName}");

                // populate the fields
                var playerProfileSO = ReusableData.Instance.GetPlayerProfileSO();
                playerProfileSO.SetPlayerProfile(new PlayerProfile() { DisplayName = signinRes.DisplayName, Email = _email });

                Debug.Log($"First time signin in status: {signinRes.IsFirstTimeSignin}");

                OnSigninSuccess?.Invoke(signinRes);
            });
        }


        public void HandleValueChanged_Email(string newValue)
        {
            _email = newValue;
        }

        public void HandleValueChanged_Password(string newValue)
        {
            _password = newValue;
        }

        #endregion
    }
}