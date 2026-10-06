using UnityEngine;

namespace AwakenedRealm.Services.Authentication
{
    /// <summary>
    /// Non-secret Google OAuth configuration surface.
    ///
    /// The Google sign-in flow needs the OAuth 2.0 *Web* client ID that is
    /// registered for this title. That value is required to request a
    /// server auth code, and it must also be entered (with its secret) in the
    /// PlayFab Game Manager Google Add-on. The client ID itself is not a
    /// secret and is safe to ship.
    ///
    /// Values are resolved in this order (first non-empty wins):
    ///   1. PlayerPrefs key <see cref="WebClientIdPrefsKey"/> (runtime override).
    ///   2. The serialized web client id on this asset (Resources/GoogleAuthConfig).
    ///
    /// No client secret is ever stored here.
    /// </summary>
    public class GoogleAuthConfig : ScriptableObject
    {
        /// <summary>
        /// PlayerPrefs key a build/deploy step or debug menu may use to inject
        /// the web client id without rebuilding. Kept out of source control.
        /// </summary>
        public const string WebClientIdPrefsKey = "awakened_google_web_client_id";

        [Tooltip("OAuth 2.0 Web application client ID from Google Cloud Console. " +
                 "Must match the client id configured in the PlayFab Google Add-on.")]
        [SerializeField] private string _webClientId;

        public string WebClientId
        {
            get
            {
                string overrideId = PlayerPrefs.GetString(WebClientIdPrefsKey, string.Empty);
                if (!string.IsNullOrEmpty(overrideId)) return overrideId;
                return _webClientId;
            }
        }

        public bool IsConfigured => !string.IsNullOrEmpty(WebClientId);

        /// <summary>
        /// Loads the first GoogleAuthConfig found under any Resources folder, or
        /// null if none exists (Google sign-in will report ConfigRequired).
        /// </summary>
        public static GoogleAuthConfig Load()
        {
            return Resources.Load<GoogleAuthConfig>("GoogleAuthConfig");
        }
    }
}
