using System;
using System.Reflection;
using AwakenedRealm.Models;
using UnityEngine;

namespace AwakenedRealm.Services.Authentication
{
    /// <summary>
    /// Google credential provider backed by the official Google Play Games
    /// plugin for Unity (v2), reached through reflection so the project compiles
    /// with or without the package installed.
    ///
    /// When the plugin is absent this provider reports itself unavailable and
    /// <see cref="GoogleSignInService"/> falls back to the native Android
    /// bridge (<see cref="NativeBridgeGoogleSignInProvider"/>).
    ///
    /// Plugin flow:
    ///   PlayGamesPlatform.Activate() -> PlayGamesPlatform.Instance.Authenticate()
    ///   -> RequestServerSideAccess(refresh, clientId, onAuthCode).
    /// </summary>
    public class PlayGamesGoogleSignInProvider : IGoogleSignInProvider
    {
        private readonly bool _pluginPresent;

        public PlayGamesGoogleSignInProvider()
        {
            _pluginPresent = FindType("GooglePlayGames.PlayGamesPlatform") != null;
        }

        public bool IsAvailable => _pluginPresent;

        public void RequestServerAuthCode(GoogleAuthConfig config, Action<GoogleCredentialResult> onComplete)
        {
            if (!_pluginPresent)
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.ProviderUnavailable,
                    "Google Play Games plugin is not installed."));
                return;
            }

#if !UNITY_ANDROID || UNITY_EDITOR
            onComplete?.Invoke(GoogleCredentialResult.Failure(
                AuthFailureKind.ProviderUnavailable,
                "Google Play Games sign-in requires an Android device."));
#else
            try
            {
                Run(config != null ? config.WebClientId : null, onComplete);
            }
            catch (Exception e)
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.CredentialFailed,
                    "Google Play Games sign-in threw: " + e.Message));
            }
#endif
        }

#if UNITY_ANDROID && !UNITY_EDITOR
        private void Run(string clientId, Action<GoogleCredentialResult> onComplete)
        {
            var platformType = FindType("GooglePlayGames.PlayGamesPlatform");

            var activate = platformType.GetMethod("Activate", BindingFlags.Public | BindingFlags.Static);
            var authenticate = platformType.GetMethod("Authenticate", BindingFlags.Public | BindingFlags.Instance);
            var instanceProp = platformType.GetProperty("Instance", BindingFlags.Public | BindingFlags.Static);
            var statusType = FindType("GooglePlayGames.BasicApi.SignInStatus");
            if (activate == null || authenticate == null || instanceProp == null || statusType == null)
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.ProviderUnavailable,
                    "Google Play Games plugin is present but its API shape is unsupported."));
                return;
            }

            activate.Invoke(null, null);
            object platform = instanceProp.GetValue(null);

            // Build Action<SignInStatus> that forwards to our object callback.
            Action<object> onAuth = statusObj =>
            {
                string statusName = statusObj != null ? statusObj.ToString() : "Failed";
                if (statusName != "Success")
                {
                    var kind = statusName == "Canceled"
                        ? AuthFailureKind.Cancelled
                        : AuthFailureKind.ProviderUnavailable;
                    onComplete?.Invoke(GoogleCredentialResult.Failure(
                        kind, "Play Games authenticate failed: " + statusName));
                    return;
                }
                RequestServerSideAccess(platformType, platform, clientId, onComplete);
            };

            var authDelegate = TypedCallback.Create(statusType, onAuth);
            authenticate.Invoke(platform, new object[] { authDelegate });
        }

        private void RequestServerSideAccess(
            Type platformType, object platform, string clientId,
            Action<GoogleCredentialResult> onComplete)
        {
            var method = platformType.GetMethod(
                "RequestServerSideAccess", BindingFlags.Public | BindingFlags.Instance);
            if (method == null)
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.ProviderUnavailable,
                    "Google Play Games plugin lacks RequestServerSideAccess."));
                return;
            }

            Action<string> callback = code =>
            {
                if (string.IsNullOrEmpty(code))
                {
                    onComplete?.Invoke(GoogleCredentialResult.Failure(
                        AuthFailureKind.CredentialFailed,
                        "Play Games returned an empty server auth code."));
                }
                else
                {
                    onComplete?.Invoke(GoogleCredentialResult.Success(code));
                }
            };

            var parms = method.GetParameters();
            if (parms.Length == 2)
            {
                // (bool forceRefreshToken, Action<string> callback)
                method.Invoke(platform, new object[] { false, callback });
            }
            else if (parms.Length == 3)
            {
                // (bool forceRefreshToken, string clientId, Action<string> callback)
                method.Invoke(platform, new object[] { false, clientId, callback });
            }
            else
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.ProviderUnavailable,
                    "Unsupported RequestServerSideAccess signature."));
            }
        }
#endif

        internal static Type FindType(string fullName)
        {
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                var t = asm.GetType(fullName);
                if (t != null) return t;
            }
            return null;
        }

#if UNITY_ANDROID && !UNITY_EDITOR
        /// <summary>
        /// Creates a closed <c>Action&lt;TArg&gt;</c> delegate that forwards to an
        /// <see cref="Action{object}"/>, so reflection-based calls can satisfy
        /// enum-typed callbacks (e.g. <c>Action&lt;SignInStatus&gt;</c>) without
        /// a compile-time dependency on the plugin's types.
        /// </summary>
        private static class TypedCallback
        {
            public static Delegate Create(Type argType, Action<object> target)
            {
                var holderType = typeof(Holder<>).MakeGenericType(argType);
                var holder = Activator.CreateInstance(holderType);
                holderType.GetField("Target").SetValue(holder, target);
                var fwd = holderType.GetMethod("Forward", BindingFlags.Public | BindingFlags.Instance);
                return Delegate.CreateDelegate(typeof(Action<>).MakeGenericType(argType), holder, fwd);
            }

            private class Holder<T>
            {
                // ReSharper disable once UnusedMember.Global
                public Action<object> Target;

                // ReSharper disable once UnusedMember.Local
                public void Forward(T value) => Target?.Invoke(value);
            }
        }
#endif
    }
}
