using System;
using AwakenedRealm.Models;
using UnityEngine;

namespace AwakenedRealm.Services.Authentication
{
    /// <summary>
    /// Google credential provider that delegates to a native Android bridge.
    ///
    /// Bridge contract (implemented by a plugin under
    /// Assets/Plugins/Android/AwakenedAuth or by an installed Google sign-in
    /// plugin that registers an equivalent entry point):
    ///
    ///   Class:   com.awakenedrealms.auth.GoogleSignInBridge
    ///   Method:  static void requestServerAuthCode(
    ///                com.unity3d.player.UnityPlayer activity,
    ///                String webClientId,
    ///                String unityCallbackObjectName)
    ///
    /// The bridge must send the result back via
    /// UnitySendMessage(unityCallbackObjectName, "OnServerAuthCode", payload)
    /// where payload is:
    ///   "OK:&lt;serverAuthCode&gt;"    - success
    ///   "CANCELLED"                    - user closed the flow
    ///   "ERROR:&lt;message&gt;"        - provider failure
    ///   "UNAVAILABLE:&lt;message&gt;"  - Play services / SDK missing
    ///
    /// Until such a bridge (or the official plugin) is present, this provider
    /// fails closed with ProviderUnavailable.
    /// </summary>
    public class NativeBridgeGoogleSignInProvider : IGoogleSignInProvider
    {
        private const string BridgeClassName = "com.awakenedrealms.auth.GoogleSignInBridge";
        private const string CallbackObjectName = "AwakenedGoogleSignInCallback";

        public bool IsAvailable
        {
            get
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                try
                {
                    using (var cls = new AndroidJavaClass(BridgeClassName))
                    {
                        return cls != null;
                    }
                }
                catch (Exception)
                {
                    return false;
                }
#else
                return false;
#endif
            }
        }

        public void RequestServerAuthCode(GoogleAuthConfig config, Action<GoogleCredentialResult> onComplete)
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                var listener = GoogleSignInCallbackGameObject.GetOrCreate();
                listener.Begin(onComplete);

                string clientId = config != null ? config.WebClientId : string.Empty;
                using (var unityPlayer = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
                using (var activity = unityPlayer.GetStatic<AndroidJavaObject>("currentActivity"))
                using (var bridge = new AndroidJavaClass(BridgeClassName))
                {
                    bridge.CallStatic("requestServerAuthCode", activity, clientId, CallbackObjectName);
                }
            }
            catch (Exception e)
            {
                onComplete?.Invoke(GoogleCredentialResult.Failure(
                    AuthFailureKind.ProviderUnavailable,
                    "Android Google sign-in bridge unavailable: " + e.Message));
            }
#else
            onComplete?.Invoke(GoogleCredentialResult.Failure(
                AuthFailureKind.ProviderUnavailable,
                "Native Google sign-in bridge is only available on Android."));
#endif
        }

#if UNITY_ANDROID && !UNITY_EDITOR
        /// <summary>
        /// Hidden GameObject that receives UnitySendMessage callbacks from the
        /// native bridge and forwards them to the pending completion.
        /// </summary>
        private sealed class GoogleSignInCallbackGameObject : MonoBehaviour
        {
            private static GoogleSignInCallbackGameObject _instance;
            private Action<GoogleCredentialResult> _pending;

            public static GoogleSignInCallbackGameObject GetOrCreate()
            {
                if (_instance != null) return _instance;
                var go = new GameObject(CallbackObjectName);
                UnityEngine.Object.DontDestroyOnLoad(go);
                _instance = go.AddComponent<GoogleSignInCallbackGameObject>();
                return _instance;
            }

            public void Begin(Action<GoogleCredentialResult> onComplete)
            {
                _pending = onComplete;
            }

            // Called by UnitySendMessage from native code.
            // ReSharper disable once UnusedMember.Local
            private void OnServerAuthCode(string payload)
            {
                var cb = _pending;
                _pending = null;
                if (cb == null) return;

                if (string.IsNullOrEmpty(payload))
                {
                    cb(GoogleCredentialResult.Failure(
                        AuthFailureKind.CredentialFailed, "Empty response from Google bridge."));
                }
                else if (payload == "CANCELLED")
                {
                    cb(GoogleCredentialResult.Failure(
                        AuthFailureKind.Cancelled, "Google sign-in cancelled."));
                }
                else if (payload.StartsWith("OK:", StringComparison.Ordinal))
                {
                    cb(GoogleCredentialResult.Success(payload.Substring(3)));
                }
                else if (payload.StartsWith("UNAVAILABLE:", StringComparison.Ordinal))
                {
                    cb(GoogleCredentialResult.Failure(
                        AuthFailureKind.ProviderUnavailable, payload.Substring(12)));
                }
                else if (payload.StartsWith("ERROR:", StringComparison.Ordinal))
                {
                    cb(GoogleCredentialResult.Failure(
                        AuthFailureKind.CredentialFailed, payload.Substring(6)));
                }
                else
                {
                    cb(GoogleCredentialResult.Failure(
                        AuthFailureKind.CredentialFailed, "Unknown bridge payload: " + payload));
                }
            }
        }
#endif
    }
}
