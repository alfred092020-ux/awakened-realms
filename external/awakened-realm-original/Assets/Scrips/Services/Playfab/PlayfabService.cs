using PlayFab;
using PlayFab.ClientModels;
using System;
using AwakenedRealm.Models;
using AwakenedRealm.Keys;
using UnityEngine;
using System.Threading.Tasks;
using System.Collections.Generic;
using Cysharp.Threading.Tasks.Triggers;

namespace AwakenedRealm.Services
{
    public static class PlayfabService
    {
        public static void SignIn(SigninRequest request, Action<SigninResult> callback)
        {
            if (request == null)
            {
                callback?.Invoke(new SigninResult()
                {
                    IsSuccess = false,
                    ErrorMsg = "Request is null"
                });
                return;
            }

            var signinReq = new LoginWithEmailAddressRequest
            {
                Email = request.Email,
                Password = request.Password,
                InfoRequestParameters = new GetPlayerCombinedInfoRequestParams
                {
                    GetPlayerProfile = true,
                }
            };

            PlayFabClientAPI.LoginWithEmailAddress(signinReq, res =>
            {
                callback?.Invoke(new SigninResult()
                {
                    IsSuccess = true,
                    DisplayName = res.InfoResultPayload.PlayerProfile.DisplayName,
                    IsFirstTimeSignin = res.NewlyCreated,
                    Provider = AuthProviderKind.Email,
                    PlayFabId = res.PlayFabId,
                });
            }, err => { callback?.Invoke(new SigninResult() { IsSuccess = false, ErrorMsg = err.ErrorMessage }); });
        }

        /// <summary>
        /// Real PlayFab Google login: accepts a server auth code previously
        /// obtained from a Google provider and calls LoginWithGoogleAccount
        /// with CreateAccount=true so a first-time Google user gets a real
        /// PlayFab account. Never fabricates a credential or a success.
        /// </summary>
        public static void SignInWithGoogleAuthCode(string serverAuthCode, Action<SigninResult> callback)
        {
            if (string.IsNullOrEmpty(serverAuthCode))
            {
                callback?.Invoke(new SigninResult
                {
                    IsSuccess = false,
                    ErrorMsg = "Google server auth code is empty",
                    FailureKind = AuthFailureKind.CredentialFailed,
                    Provider = AuthProviderKind.Google,
                });
                return;
            }

            var req = new LoginWithGoogleAccountRequest
            {
                ServerAuthCode = serverAuthCode,
                CreateAccount = true,
                InfoRequestParameters = new GetPlayerCombinedInfoRequestParams
                {
                    GetPlayerProfile = true,
                },
            };

            PlayFabClientAPI.LoginWithGoogleAccount(req, res =>
            {
                callback?.Invoke(new SigninResult
                {
                    IsSuccess = true,
                    DisplayName = res.InfoResultPayload?.PlayerProfile?.DisplayName,
                    IsFirstTimeSignin = res.NewlyCreated,
                    Provider = AuthProviderKind.Google,
                    PlayFabId = res.PlayFabId,
                });
            }, err =>
            {
                callback?.Invoke(new SigninResult
                {
                    IsSuccess = false,
                    ErrorMsg = err != null ? err.ErrorMessage : "Unknown PlayFab error",
                    ErrorCode = err != null ? (int)err.Error : (int?)null,
                    FailureKind = AuthFailureKind.PlayFabError,
                    Provider = AuthProviderKind.Google,
                });
            });
        }

        /// <summary>
        /// Links the currently authenticated PlayFab account (e.g. a guest) to a
        /// Google identity, preserving the existing account and all of its
        /// progress. forceLink is only used to recover from a stale mapping.
        /// </summary>
        public static void LinkGoogleAccount(string serverAuthCode, bool forceLink, Action<LinkResult> callback)
        {
            if (string.IsNullOrEmpty(serverAuthCode))
            {
                callback?.Invoke(new LinkResult
                {
                    IsSuccess = false,
                    ErrorMsg = "Google server auth code is empty",
                    FailureKind = AuthFailureKind.CredentialFailed,
                    Provider = AuthProviderKind.Google,
                });
                return;
            }

            var req = new LinkGoogleAccountRequest
            {
                ServerAuthCode = serverAuthCode,
                ForceLink = forceLink,
            };

            PlayFabClientAPI.LinkGoogleAccount(req, res =>
            {
                callback?.Invoke(new LinkResult
                {
                    IsSuccess = true,
                    Provider = AuthProviderKind.Google,
                });
            }, err =>
            {
                callback?.Invoke(new LinkResult
                {
                    IsSuccess = false,
                    ErrorMsg = err != null ? err.ErrorMessage : "Unknown PlayFab error",
                    ErrorCode = err != null ? (int)err.Error : (int?)null,
                    FailureKind = AuthFailureKind.PlayFabError,
                    Provider = AuthProviderKind.Google,
                });
            });
        }

        /// <summary>
        /// Attaches email/password credentials to the currently authenticated
        /// account, letting a guest upgrade into a permanent login without
        /// losing the PlayFab account or its progress.
        /// </summary>
        public static void AddUsernamePasswordToCurrentAccount(string email, string password, string username, Action<AuthResult> callback)
        {
            var req = new AddUsernamePasswordRequest
            {
                Email = email,
                Password = password,
                Username = username,
            };

            PlayFabClientAPI.AddUsernamePassword(req, res =>
            {
                callback?.Invoke(new AuthResult
                {
                    IsSuccess = true,
                    DisplayName = res.Username,
                });
            }, err =>
            {
                callback?.Invoke(new AuthResult
                {
                    IsSuccess = false,
                    ErrorMsg = err != null ? err.ErrorMessage : "Unknown PlayFab error",
                    ErrorCode = err != null ? (int)err.Error : (int?)null,
                    FailureKind = AuthFailureKind.PlayFabError,
                });
            });
        }

        /// <summary>
        /// Links the current Android device id to the authenticated account so
        /// device-bound guest recovery continues to work after upgrading.
        /// </summary>
        public static void LinkDeviceToCurrentAccount(Action<LinkResult> callback)
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            var req = new LinkAndroidDeviceIDRequest
            {
                AndroidDeviceId = PlayFabSettings.DeviceUniqueIdentifier,
                AndroidDevice = SystemInfo.deviceModel,
                OS = SystemInfo.operatingSystem,
            };

            PlayFabClientAPI.LinkAndroidDeviceID(req, res =>
            {
                callback?.Invoke(new LinkResult { IsSuccess = true, Provider = AuthProviderKind.Guest });
            }, err =>
            {
                callback?.Invoke(new LinkResult
                {
                    IsSuccess = false,
                    ErrorMsg = err != null ? err.ErrorMessage : "Unknown PlayFab error",
                    ErrorCode = err != null ? (int)err.Error : (int?)null,
                    FailureKind = AuthFailureKind.PlayFabError,
                    Provider = AuthProviderKind.Guest,
                });
            });
#else
            callback?.Invoke(new LinkResult
            {
                IsSuccess = false,
                ErrorMsg = "Device link is only available on Android",
                FailureKind = AuthFailureKind.ProviderUnavailable,
                Provider = AuthProviderKind.Guest,
            });
#endif
        }

        public static void Signup(SignupRequest request, Action<SignupResult> callback)
        {
            if (request == null)
            {
                callback?.Invoke(new SignupResult()
                {
                    IsSuccess = false,
                    ErrorMsg = "Request is null"
                });
                return;
            }

            var signupReq = new RegisterPlayFabUserRequest()
            {
                RequireBothUsernameAndEmail = false,
                DisplayName = request.DisplayName,
                Email = request.Email,
                Password = request.Password,
                InfoRequestParameters = new GetPlayerCombinedInfoRequestParams()
                {
                    GetPlayerProfile = true,
                }
            };

            PlayFabClientAPI.RegisterPlayFabUser(signupReq, res =>
            {
                callback?.Invoke(new SignupResult()
                {
                    IsSuccess = true,
                    DisplayName = request.DisplayName,
                });
            }, err =>
            {
                callback?.Invoke(new SignupResult()
                {
                    IsSuccess = false,
                    ErrorMsg = err.ErrorMessage
                });
            });
        }


        public static async Task<bool> UpdateHeroProfile(List<HeroProfile> heroProfileList)
        {
            // Convert hero profile to JSON
            string data = JsonHelper.ToJsonList<HeroProfile>(heroProfileList);

            // Create the request to update the user data
            var updateReq = new UpdateUserDataRequest
            {
                Data = new Dictionary<string, string>
        {
            { PlayfabKeys.HeroProfileKey, data }
        }
            };

            // Create a TaskCompletionSource to handle the async callback
            var taskCompletionSource = new TaskCompletionSource<bool>();

            // Make the API call to update user data
            PlayFabClientAPI.UpdateUserData(updateReq, res =>
            {
                // On success, set the result to true
                Debug.Log("Hero profile updated successfully!");
                taskCompletionSource.SetResult(true);  // Complete the task with success
            },
            err =>
            {
                // On error, set the result to false
                Debug.LogError("Error updating hero profile: " + err.GenerateErrorReport());
                taskCompletionSource.SetResult(false);  // Complete the task with failure
            });

            // Await the TaskCompletionSource to return the result
            return await taskCompletionSource.Task;
        }
        public static async Task<bool> UpdatePlayerData(PlayerData playerData)
        {
            var jsonData = JsonHelper.ToJson<PlayerData>(playerData);

            var req = new UpdateUserDataRequest
            {
                Data = new Dictionary<string, string>
                {
                    {PlayfabKeys.PlayerDataKey,jsonData}
                }
            };

            var taskCompletionSource = new TaskCompletionSource<bool>();

            PlayFabClientAPI.UpdateUserData(req, res =>
            {
                taskCompletionSource.SetResult(true);
            }, err =>
            {
                taskCompletionSource.SetResult(false);
            });

            return await taskCompletionSource.Task;
        }
        public static async Task<PlayerData> FetchPlayerData()
        {
            var req = new GetUserDataRequest
            {
                Keys = new List<string> { PlayfabKeys.PlayerDataKey }
            };

            var taskCompletionSource = new TaskCompletionSource<PlayerData>();

            PlayFabClientAPI.GetUserData(req, res =>
            {
                if (res.Data.ContainsKey(PlayfabKeys.PlayerDataKey) == false) taskCompletionSource.SetResult(null);
                else taskCompletionSource.SetResult(JsonHelper.FromJson<PlayerData>(res.Data[PlayfabKeys.PlayerDataKey].Value));
            },
            err =>
            {
                taskCompletionSource.SetResult(JsonHelper.FromJson<PlayerData>(null));
            }
            );

            return await taskCompletionSource.Task;
        }


        public static async Task<HeroProfile> FetchHeroProfile()
        {
            // Prepare the request to fetch user data based on the keys
            var fetchReq = new GetUserDataRequest
            {
                Keys = new List<string> { PlayfabKeys.HeroProfileKey }
            };

            // Call PlayFab API asynchronously
            var taskCompletionSource = new TaskCompletionSource<HeroProfile>();

            PlayFabClientAPI.GetUserData(fetchReq, res =>
            {
                // Check if the data is present
                if (res.Data != null && res.Data.ContainsKey(PlayfabKeys.HeroProfileKey))
                {
                    // Successfully fetched the hero data
                    string heroDataJson = res.Data[PlayfabKeys.HeroProfileKey].Value;
                    HeroProfile heroProfile = JsonUtility.FromJson<HeroProfile>(heroDataJson);
                    taskCompletionSource.SetResult(heroProfile);  // Return the HeroProfile
                    //Debug.Log($"Hero data fetched: {heroProfile.DisplayName}");
                }
                else
                {
                    // No data found or incorrect key
                    taskCompletionSource.SetResult(null);
                    Debug.LogWarning("No hero profile data found.");
                }
            }, err =>
            {
                // Handle error
                taskCompletionSource.SetException(new Exception("Failed to fetch hero profile data."));
                Debug.LogError($"Error fetching hero data: {err.GenerateErrorReport()}");
            });

            // Return the result as a task
            return await taskCompletionSource.Task;
        }

        public static async Task<bool> UserDataExists()
        {
            // Check if we have data already, if not then upload the new blueprint for the user to get him ongoing
            var playerDataResult = await FetchPlayerData();
            var heroProfileResult = await FetchHeroProfile();

            return !(playerDataResult == null && heroProfileResult == null);
        }

    }
}
