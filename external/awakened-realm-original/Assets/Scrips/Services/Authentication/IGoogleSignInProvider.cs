using System;

namespace AwakenedRealm.Services.Authentication
{
    /// <summary>
    /// Abstraction over whatever Google sign-in SDK is available at runtime
    /// (Google Sign-In plugin, Google Play Games sign-in, or a native Android
    /// bridge). Implementations must never fabricate a credential: a provider
    /// that cannot produce a server auth code must report failure via
    /// <see cref="GoogleCredentialResult.FailureKind"/> so the UI can surface
    /// CONFIG_REQUIRED / PROVIDER_UNAVAILABLE instead of a fake success.
    /// </summary>
    public interface IGoogleSignInProvider
    {
        /// <summary>True when the provider is ready to attempt a sign-in.</summary>
        bool IsAvailable { get; }

        /// <summary>
        /// Attempts to obtain an OAuth 2.0 server auth code for PlayFab
        /// LoginWithGoogleAccount / LinkGoogleAccount.
        /// </summary>
        void RequestServerAuthCode(GoogleAuthConfig config, Action<GoogleCredentialResult> onComplete);
    }
}
