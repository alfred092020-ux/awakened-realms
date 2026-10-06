using System;
using System.Collections.Generic;
using AwakenedRealm.Data;
using AwakenedRealm.Enums;
using AwakenedRealm.Models;
using AwakenedRealm.UI;
using Cysharp.Threading.Tasks;
using UnityEngine;

namespace AwakenedRealm
{
    public class BattleUIManager : MonoBehaviour
    {
        public static BattleUIManager Instance;

        [SerializeField] UI_HeroPlacement _heroPlacementUI;
        public UI_HeroPlacement GetHeroPlacementUI() => _heroPlacementUI;

        [SerializeField] UI_Ticket _ticketUI;
        public UI_Ticket GetTicketUI() => _ticketUI;

        public Action<List<FormationSlotSelection>> OnBattleReady;

        void Awake()
        {
            Instance = this;
        }

        async void Start()
        {
            await UniTask.WaitUntil(() => BattleManager.Instance != null);

            BattleManager.Instance.OnWaveCompleted += HandleWaveCompleted;
            BattleManager.Instance.OnWaveStarted += HandleWaveStarted;
            BattleManager.Instance.OnEnemyKilled += HandleEnemyKilled;

            _heroPlacementUI.SetUI_HeroPlacement(ReusableData.Instance.GetHeroSOCollection().GetAllHeroes());
            _heroPlacementUI.OnStartBattle += HandleBattleStarted;
            _ticketUI.SetUI_Ticket(ReusableData.Instance.GetTicketSOCollection());
        }

        void OnDisable()
        {
            if (_heroPlacementUI != null) _heroPlacementUI.OnStartBattle -= HandleBattleStarted;
            if (BattleManager.Instance != null)
            {
                BattleManager.Instance.OnWaveCompleted -= HandleWaveCompleted;
                BattleManager.Instance.OnWaveStarted -= HandleWaveStarted;
                BattleManager.Instance.OnEnemyKilled -= HandleEnemyKilled;
            }
        }

        private void HandleEnemyKilled(CharacterType type)
        {
            if (type == CharacterType.enemy) _ticketUI.IncreaseBasicTicket(5);
            else if (type == CharacterType.boss) _ticketUI.IncreaseAdvanceTicket(1);
        }

        private void HandleBattleStarted(List<FormationSlotSelection> formation)
        {
            _heroPlacementUI.DisableUI();
            OnBattleReady?.Invoke(formation);
        }

        private void HandleWaveCompleted(WaveData waveData)
        {
            Debug.Log($"Wave {waveData.CurrentWave} has been completed");
        }

        private void HandleWaveStarted(WaveData waveData)
        {
            Debug.Log($"Wave {waveData.CurrentWave} has been started");
        }
    }
}
