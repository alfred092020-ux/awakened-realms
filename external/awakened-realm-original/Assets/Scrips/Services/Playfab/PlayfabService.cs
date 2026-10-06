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
                    IsFirstTimeSignin = res.NewlyCreated
                });
            }, err => { callback?.Invoke(new SigninResult() { IsSuccess = false, ErrorMsg = err.ErrorMessage }); });
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