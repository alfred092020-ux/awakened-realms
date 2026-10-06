using AwakenedRealm.Models;
using UnityEngine;

namespace AwakenedRealm.Scriptables
{
    [CreateAssetMenu(fileName = "Player Profile", menuName = "Scriptables/New Player Profile")]
    public class PlayerProfileSO : ScriptableObject
    {
        [SerializeField] PlayerData _playerData;

        public void SetPlayerProfile(PlayerProfile profile)
        {
            _playerData.Profile = profile;
        }
        public void SetPlayerWallet(PlayerWallet wallet)
        {
            _playerData.Wallet = wallet;
        }

        public void SetPlayerData(PlayerData data)
        {
            _playerData = data;
        }


        public PlayerData GetPlayerData() => _playerData;
    }

}