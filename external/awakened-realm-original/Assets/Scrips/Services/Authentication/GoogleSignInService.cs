using System;
using AwakenedRealm.Models;
using PlayFab;
using PlayFab.ClientModels;

namespace AwakenedRealm.Services.Authentication
{
    /// <summary>
    /// Coordinates Google sign-in: picks the best available credential provider
    /// (official Google Play Games plugin -> native Android bridge), obtains a
    /// server auth code, then calls the PlayFab client API.
    ///
    /// Failure contract (fail-closed, never a fake success):
    ///   * No OAuth web client id configured            -> ConfigRequired
    ///   * No provider (plugin + bridge) on this device -> ProviderUnavailable
    ///   * User cancels / bridge fails                  -> Cancelled / CredentialFailed
    ///   * PlayFab rejects the server auth code         -> PlayFabError
    /// </summary>
    public static class GoogleSignInService
    {
        private static IGoogleSignInProvider _providerOverride;
        private static IGoogleSignInProvider _cachedProvider;

        /// <summary>
        /// Allows tests or a future settings UI to pin a specific provider.
        /// Pass null to restore automatic selection.
        /// </summary>
        public static void SetProviderOverride(IGoogleSignInProvider provider)
        {
            _providerOverride = provider;
        }

        /// <summary>
        /// Picks the first usable provider. Ordering matters: the official
        /// Play Games plugin wins because it owns the OAuth flow; the custom
        /// native bridge is the fallback when the plugin is absent.
        /// </summary>
        public static IGoogleSignInProvider ResolveProvider()
        {
            if (_providerOverride != null) return _providerOverride;
            if (_cachedProvider != null) return _cachedProvider;

            var gpg = new PlayGamesGoogleSignInProvider();
            if (gpg.IsAvailable)
            {
                _cachedProvider = gpg;
                return _cachedProvider;
            }

            var native = new NativeBridgeGoogleSignInProvider();
            _cachedProvider = native; // cache even if unavailable; bridges don't appear mid-session
            return _cachedProvider;
        }

        /// <summary>
        /// True only when a web client id is configured AND some provider
        /// reports itself usable. UI can use this to grey-out the Google button.
        /// </summary>
        public static bool IsGoogleSignInReady()
        {
            var cfg = GoogleAuthConfig.Load();
            return cfg != null && cfg.IsConfigured && ResolveProvider().IsAvailable;
        }

        /// <summary>
        /// Full Google -> PlayFab sign-in. Obtains a server auth code, then calls
        /// <see cref="PlayFabClientAPI.LoginWithGoogleAccount"/> with
        /// CreateAccount=true so a first-time Google user gets a real account.
        /// The callback receives the same <see cref="SigninResult"/> shape as
        /// email/guest sign-in so the manager routes it identically.
        /// </summary>
        public static void SignInWithGoogle(Action<SigninResult> callback)
        {
            GetGoogleCredential(cred =>
            {
                if (!cred.IsSuccess)
                {
                    callback?.Invoke(new SigninResult
                    {
                        IsSuccess = false,
                        ErrorMsg = cred.ErrorMsg,
                        FailureKind = cred.FailureKind,
                        Provider = AuthProviderKind.Google,
                    });
                    return;
                }

                PlayfabService.SignInWithGoogleAuthCode(cred.ServerAuthCode, callback);
            });
        }

        /// <summary>
        /// Links the currently authenticated PlayFab account to a Google
        /// identity, preserving the existing account (and its progress).
        /// </summary>
        public static void LinkCurrentAccountToGoogle(Action<LinkResult> callback)
        {
            GetGoogleCredential(cred =>
            {
                if (!cred.IsSuccess)
                {
                    callback?.Invoke(new LinkResult
                    {
                        IsSuccess = false,
                        ErrorMsg = cred.ErrorMsg,
                        FailureKind = cred.FailureKind,
                        Provider = AuthProviderKind.Google,
                    });
                    return;
                }

                PlayfabService.LinkGoogleAccount(cred.ServerAuthCode, false, callback);
            });
        }

        /// <summary>
        /// Shared credential acquisition used by both login and link. Fails
        /// closed with ConfigRequired when no web client id exists.
        /// </summary>
        private static void GetGoogleCredential(Action<GoogleCredentialResult> onComplete)
        {
            var cfg = GoogleAuthConfig.Load();
            if (cfg == null || !cfg.IsConfigured)
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.ConfigRequired,
                    "Google sign-in requires an OAuth web client id (GoogleAuthConfig)."));
                return;
            }

            var provider = ResolveProvider();
            if (provider == null || !provider.IsAvailable)
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.ProviderUnavailable,
                    "No Google sign-in provider is available on this device."));
                return;
            }

            provider.RequestServerAuthCode(cfg, onComplete);
        }

        /// <summary>Builds a consistent GetPlayerCombinedInfoRequestParams for Google login.</summary>
        internal static GetPlayerCombinedInfoRequestParams GoogleInfoParams()
        {
            return new GetPlayerCombinedInfoRequestParams
            {
                GetPlayerProfile = true,
            };
        }
    }
}
