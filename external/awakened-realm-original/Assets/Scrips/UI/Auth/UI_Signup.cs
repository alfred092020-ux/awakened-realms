using System;
using AwakenedRealm.Models;
using AwakenedRealm.Services;
using Cysharp.Threading.Tasks;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_Signup : MonoBehaviour
    {
        [SerializeField] private Button _signupBtn;
        [SerializeField] private Button _alreadyHaveAnAccountBtn;

        [SerializeField] private UI_Slide _slideUI;
        //[SerializeField] private Button _signinMeAutomaticallyAfterCreatingAccountBtn;

        private bool _signinAfterCreatingAccount = false;

        private string _displayName;
        private string _email;
        private string _password;
        private string _confirmPassword;

        public Action<SignupResult> OnSignupSuccess;
        public Action OnSignupFailed;

        public UnityEvent OnSwitch;

        private CanvasGroup _canvasGroup;

        private void Awake()
        {
            // UI_Slide owns this group; used to ignore Back while sliding out.
            _canvasGroup = GetComponent<CanvasGroup>();
        }

        private void OnEnable()
        {
            _signupBtn.onClick.AddListener(HandleSignup);
            _alreadyHaveAnAccountBtn.onClick.AddListener(HandleAlreadyHaveAnAccount);
            //_signinMeAutomaticallyAfterCreatingAccountBtn.onClick.AddListener(HandleAutoSignin);
            ResetFields();
        }


        private void OnDisable()
        {
            _signupBtn.onClick.RemoveListener(HandleSignup);
            _alreadyHaveAnAccountBtn.onClick.RemoveListener(HandleAlreadyHaveAnAccount);
            //_signinMeAutomaticallyAfterCreatingAccountBtn.onClick.RemoveListener(HandleAutoSignin);
        }

        private void Update()
        {
            // Android system Back returns to Login while this panel is showing.
            if (!Input.GetKeyDown(KeyCode.Escape)) return;
            if (_canvasGroup == null) _canvasGroup = GetComponent<CanvasGroup>();
            if (_canvasGroup != null && _canvasGroup.alpha <= 0.9f) return;
            HandleAlreadyHaveAnAccount();
        }


        public void SetUI_Signup(bool isEnabled = false)
        {
            if (isEnabled) _slideUI.Execute();
            else _slideUI.Undo();
        }

        private (bool, string) AllFieldsAreOk()
        {
            if (_password != _confirmPassword) return (false, "Passwords don't match...");
            if (_email == string.Empty || _email == string.Empty || _password == string.Empty ||
                _confirmPassword == string.Empty) return (false, "Make sure all fields are filled...");

            return (true, "");
        }

        private void ResetFields()
        {
            _email = _password = _confirmPassword = _displayName = string.Empty;
        }


        #region Listeners

        public void HandleAutoSignin(Image dotImg)
        {
            _signinAfterCreatingAccount = !_signinAfterCreatingAccount;

            dotImg.gameObject.SetActive(_signinAfterCreatingAccount);

            // if true then the user will automatically be signed in to the game without using the dedicated signin panel
        }


        private void HandleAlreadyHaveAnAccount()
        {
            Debug.Log($"Switch invoked");
            OnSwitch?.Invoke();
        }

        private async void HandleSignup()
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


            loadingUI?.SetUI_Text("Signing you up...");
            loadingUI?.SetUI_LoadingAnimation(true);

            // call the playfab service API
            PlayfabService.Signup(new SignupRequest()
            {
                DisplayName = _displayName,
                Email = _email,
                Password = _password
            }, async signupRes =>
            {
                if (signupRes.IsSuccess == false)
                {
                    // show the error UI
                    loadingUI?.SetUI_Text($"Couldn't sign you up, {signupRes.ErrorMsg}");
                    loadingUI?.SetUI_LoadingAnimation(true);
                    await UniTask.WaitForSeconds(3.0f);
                    loadingUI.SetUI_LoadingAnimation(false);
                    Debug.Log($"Signup failed, err: {signupRes.ErrorMsg}");
                    OnSignupFailed?.Invoke();
                    return;
                }

                // show success UI
                loadingUI?.SetUI_Text($"Signed in, {signupRes.DisplayName}");
                loadingUI?.SetUI_LoadingAnimation(true);
                await UniTask.WaitForSeconds(3.0f);
                loadingUI.SetUI_LoadingAnimation(false);
                Debug.Log($"Signed up successfully, displayName: {signupRes.DisplayName}");
                OnSignupSuccess?.Invoke(signupRes);
            });
        }


        public void HandleValueChanged_DisplayName(string newValue)
        {
            _displayName = newValue;
        }

        public void HandleValueChanged_Email(string newValue)
        {
            _email = newValue;
        }

        public void HandleValueChanged_Password(string newValue)
        {
            _password = newValue;
        }

        public void HandleValueChanged_ConfirmPassword(string newValue)
        {
            _confirmPassword = newValue;
        }

        #endregion
    }
}
