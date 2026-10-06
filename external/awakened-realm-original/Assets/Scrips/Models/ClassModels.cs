using System;
using AwakenedRealm.Enums;
using AwakenedRealm.Scriptables;
using NUnit.Framework;
using Unity.VisualScripting.Antlr3.Runtime.Misc;
using UnityEngine;

namespace AwakenedRealm.Models
{
    #region Playfab Models

    /// <summary>
    /// Which identity provider produced a successful (or attempted) sign-in.
    /// </summary>
    public enum AuthProviderKind
    {
        Unknown = 0,
        Email = 1,
        Guest = 2,
        Google = 3,
        GooglePlayGames = 4,
    }

    /// <summary>
    /// Coarse failure classification so UI can distinguish provider/config
    /// problems (retryable, actionable) from PlayFab rejections without
    /// parsing error strings.
    /// </summary>
    public enum AuthFailureKind
    {
        None = 0,
        /// <summary>PlayFab returned an error response (bad credentials, throttling, etc).</summary>
        PlayFabError = 1,
        /// <summary>Required external configuration is absent (e.g. Google OAuth web client id).</summary>
        ConfigRequired = 2,
        /// <summary>The sign-in provider (SDK, Play services, platform) is unavailable.</summary>
        ProviderUnavailable = 3,
        /// <summary>User cancelled the provider sign-in flow.</summary>
        Cancelled = 4,
        /// <summary>The provider could not produce a valid credential.</summary>
        CredentialFailed = 5,
    }

    public class AuthResult
    {
        public bool IsSuccess;
        public string ErrorMsg;
        public string DisplayName;
        public int? ErrorCode;
        public AuthFailureKind FailureKind = AuthFailureKind.None;
    }

    public class AuthRequest
    {
        public string Email;
        public string Password;
        public string DisplayName;
    }

    // RESULTS

    public class SigninResult : AuthResult
    {
        public bool IsFirstTimeSignin = false;

        /// <summary>Provider that produced this session (Email, Guest, Google, ...).</summary>
        public AuthProviderKind Provider = AuthProviderKind.Unknown;

        /// <summary>PlayFabId of the authenticated account (useful for link UI).</summary>
        public string PlayFabId;

        /// <summary>True when the session was created by an anonymous/guest credential.</summary>
        public bool IsGuest => Provider == AuthProviderKind.Guest;
    }

    public class SignupResult : AuthResult
    {
    }

    /// <summary>
    /// Result of linking an additional identity provider onto the currently
    /// authenticated PlayFab account (the account, and its progress, is preserved).
    /// </summary>
    public class LinkResult : AuthResult
    {
        public AuthProviderKind Provider = AuthProviderKind.Unknown;
    }

    // REQUESTS

    public class SigninRequest : AuthRequest
    {
    }

    public class SignupRequest : AuthRequest
    {
        public bool IsAnonymous = false;
    }

    #endregion


    #region Game Models

    [Serializable]
    public class WaveData
    {
        public int CurrentWave;
        public float AdditionInEachStatPerWave = 2.0f;
        public HeroStats EnemyStats;  // we can use these to increase them per wave, would be easier
        public HeroStats BossStats;  // for boss appearing after n number of waves
        public int TotalWavesBeforeBossAppears = 10;

        public float BossScaleMultiplier = 2.0f;
    }

    [Serializable]
    public class AttackInfo
    {
        public HeroController TargetCharacter;
        public HeroStats AttackerStats;
        public HeroStats ReceiverStats;
        //public HeroSO HeroSOData;
    }

    [Serializable]
    public class HeroProfile
    {
        public string HeroName;

        [Tooltip("will be critical and most useful if the name is changed somehow later in the game so it won't affect our data in any way")]
        public string HeroID;
        public int HeroLevel = 0;
        public HeroRank Rank;
        public HeroCategory Category;
        public HeroRarity Rarity;
        public HeroStats Stats;

        public bool IsUnlocked;
    }

    [Serializable]
    public class HeroStats
    {

        public float Health;    // HP: The hero's health, represents how much damage they can take before being defeated.

        public float ATK;       // ATK: The hero's attack power, determines the damage they deal to enemies.

        public float DEF;       // DEF: The hero's defense, reduces the amount of damage they take from enemies.

        // ADVANCE STATS
        public float MAG;       // MAG: The hero's magic power, used to calculate damage for magic or elemental attacks.

        public float CRIT;      // CRIT: The hero's critical hit chance, determines the probability of landing a critical hit (extra damage).

        public float RES;       // RES: The hero's resistance to status effects (like poison, burn, etc.), lowers the duration/effect of debuffs.

        public float SPD;       // SPD: The hero's speed, affects how quickly they can act (turn order, attack speed, etc.).
    }


    #endregion



    #region PlayerModels

    [Serializable]
    public class PlayerProfile
    {
        public string DisplayName;
        public string Email;
        public string Level;

    }

    [Serializable]
    public class PlayerData
    {
        public PlayerProfile Profile;
        public PlayerWallet Wallet;
    }


    [Serializable]
    public class PlayerWallet
    {
        public int BasicTickets;
        public int AdvanceTickets;
    }



    // [Serializable]
    // public class PlayerRoster
    // {

    // }


    #endregion



}
