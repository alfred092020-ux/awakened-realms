using AwakenedRealm.Models;

namespace AwakenedRealm.Services.Authentication
{
    /// <summary>
    /// Outcome of asking a Google provider for a server auth credential.
    /// <see cref="IsSuccess"/> is true only when a real <see cref="ServerAuthCode"/>
    /// was obtained from the provider; every failure carries a machine-readable
    /// <see cref="FailureKind"/> plus a human-readable <see cref="ErrorMsg"/>.
    /// </summary>
    public class GoogleCredentialResult
    {
        public bool IsSuccess;
        public string ServerAuthCode;
        public AuthFailureKind FailureKind = AuthFailureKind.None;
        public string ErrorMsg;

        public static GoogleCredentialResult Success(string serverAuthCode)
        {
            return new GoogleCredentialResult { IsSuccess = true, ServerAuthCode = serverAuthCode };
        }

        public static GoogleCredentialResult Failure(AuthFailureKind kind, string message)
        {
            return new GoogleCredentialResult { IsSuccess = false, FailureKind = kind, ErrorMsg = message };
        }
    }
}
