using System;
using AwakenedRealm.Models;
using PlayFab;
using PlayFab.ClientModels;
using UnityEngine;

namespace AwakenedRealm.Services.Authentication
{
    /// <summary>
    /// Stable, device-bound guest login through the PlayFab Client API.
    ///
    /// Primary credential (Android): LoginWithAndroidDeviceID with
    /// CreateAccount=true. The device id is PlayFabSettings.DeviceUniqueIdentifier
    /// which maps to the Android Settings.Secure ANDROID_ID, stable per app
    /// install and automatically cleared/reset on uninstall — exactly the
    /// "same installation" semantics required.
    ///
    /// Fallback (non-Android/editor/compile-time): LoginWithCustomID backed by
    /// a persisted GUID in PlayerPrefs, so repeated launches on the same
    /// machine hit the same PlayFab account instead of creating a new one.
    /// </summary>
    public static class GuestAuthService
    {
        private const string CustomIdPrefsKey = "awakened_guest_custom_id";

        /// <summary>
        /// Returns the same <see cref="SigninResult"/> shape used by email
        /// sign-in so the auth manager routes guest login through the identical
        /// success pipeline (InitializeHeroDataOnBackend -> MainMenu).
        /// </summary>
        public static void SignInAsGuest(Action<SigninResult> callback)
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            SignInWithAndroidDeviceId(callback);
#else
            SignInWithPersistedCustomId(callback);
#endif
        }

#if UNITY_ANDROID && !UNITY_EDITOR
        private static void SignInWithAndroidDeviceId(Action<SigninResult> callback)
        {
            string deviceId = PlayFabSettings.DeviceUniqueIdentifier;
            if (string.IsNullOrEmpty(deviceId))
            {
                callback?.Invoke(new SigninResult
                {
                    IsSuccess = false,
                    ErrorMsg = "Android device id unavailable",
                    FailureKind = AuthFailureKind.ProviderUnavailable,
                    Provider = AuthProviderKind.Guest,
                });
                return;
            }

            var req = new LoginWithAndroidDeviceIDRequest
            {
                AndroidDeviceId = deviceId,
                AndroidDevice = SystemInfo.deviceModel,
                OS = SystemInfo.operatingSystem,
                CreateAccount = true,
                InfoRequestParameters = new GetPlayerCombinedInfoRequestParams
                {
                    GetPlayerProfile = true,
                },
            };

            PlayFabClientAPI.LoginWithAndroidDeviceID(req,
                res => callback?.Invoke(ToSigninResult(res)),
                err => callback?.Invoke(ToError(err)));
        }
#endif

        /// <summary>
        /// Non-Android/editor fallback: a per-installation GUID stored in
        /// PlayerPrefs keeps the guest account stable across launches. It is
        /// deterministic per installed app data, never random per launch.
        /// </summary>
        private static void SignInWithPersistedCustomId(Action<SigninResult> callback)
        {
            string customId = PlayerPrefs.GetString(CustomIdPrefsKey, string.Empty);
            if (string.IsNullOrEmpty(customId))
            {
                customId = "guest-" + Guid.NewGuid().ToString("N");
                PlayerPrefs.SetString(CustomIdPrefsKey, customId);
                PlayerPrefs.Save();
            }

            var req = new LoginWithCustomIDRequest
            {
                CustomId = customId,
                CreateAccount = true,
                InfoRequestParameters = new GetPlayerCombinedInfoRequestParams
                {
                    GetPlayerProfile = true,
                },
            };

            PlayFabClientAPI.LoginWithCustomID(req,
                res => callback?.Invoke(ToSigninResult(res)),
                err => callback?.Invoke(ToError(err)));
        }

        private static SigninResult ToSigninResult(LoginResult res)
        {
            return new SigninResult
            {
                IsSuccess = true,
                DisplayName = res.InfoResultPayload?.PlayerProfile?.DisplayName,
                IsFirstTimeSignin = res.NewlyCreated,
                Provider = AuthProviderKind.Guest,
                PlayFabId = res.PlayFabId,
            };
        }

        private static SigninResult ToError(PlayFabError err)
        {
            return new SigninResult
            {
                IsSuccess = false,
                ErrorMsg = err != null ? err.ErrorMessage : "Unknown PlayFab error",
                ErrorCode = err != null ? (int)err.Error : (int?)null,
                FailureKind = AuthFailureKind.PlayFabError,
                Provider = AuthProviderKind.Guest,
            };
        }
    }
}
