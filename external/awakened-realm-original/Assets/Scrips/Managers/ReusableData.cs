using AwakenedRealm.Scriptables;
using JetBrains.Annotations;
using UnityEngine;

namespace AwakenedRealm.Data
{
    public class ReusableData : MonoBehaviour
    {
        public static ReusableData Instance;

        [SerializeField] PlayerProfileSO _playerProfileSO;
        public PlayerProfileSO GetPlayerProfileSO() => _playerProfileSO;

        [SerializeField] HeroSOCollection _heroSOCollection;
        public HeroSOCollection GetHeroSOCollection() => _heroSOCollection;

        [SerializeField] TicketSOCollection _ticketSOCollection;
        public TicketSOCollection GetTicketSOCollection() => _ticketSOCollection;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(this.gameObject);
            }
            else
            {
                Instance = this;
                DontDestroyOnLoad(this.gameObject);
            }
        }
    }

}