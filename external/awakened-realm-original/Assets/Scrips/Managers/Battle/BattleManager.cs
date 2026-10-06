using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using AwakenedRealm.Data;
using AwakenedRealm.Enums;
using AwakenedRealm.Models;
using AwakenedRealm.Scriptables;
using Cysharp.Threading.Tasks;
using UnityEngine;

namespace AwakenedRealm
{
    public class BattleManager : MonoBehaviour
    {
        public static BattleManager Instance;

        [SerializeField] Transform[] _heroSpawnTransforms;
        [SerializeField] Transform[] _enemySpawnTransforms;
        [SerializeField] HeroController _heroPrefab;
        [SerializeField] LayerMask _heroLayermask;
        [SerializeField] LayerMask _planeLayermask;

        [Tooltip("Dead characters are moved here after leaving the active line.")]
        [SerializeField] Transform _deadCharactersTransform;

        readonly List<HeroController> _spawnedHeroes = new List<HeroController>();
        public IReadOnlyList<HeroController> GetSpawnedHeroes() => _spawnedHeroes;

        [SerializeField] int _totalActiveHeroesAtATime = FormationSlotSelection.MaxPartySize;

        bool _areHeroesSpawned;
        bool _areEnemiesSpawned;

        [SerializeField] List<HeroController> _readyHeroes = new List<HeroController>();
        [SerializeField] List<HeroController> _readyEnemies = new List<HeroController>();

        List<FormationSlotSelection> _selectedFormation = new List<FormationSlotSelection>();

        public int GetCurrentWave() => _waveData.CurrentWave;

        [SerializeField] WaveData _waveData;
        [SerializeField] Transform[] _bossSpawnTransforms;

        public Action<WaveData> OnWaveCompleted;
        public Action<WaveData> OnWaveStarted;
        public Action<CharacterType> OnEnemyKilled;

        void Awake()
        {
            Instance = this;
        }

        void Start()
        {
            _areEnemiesSpawned = _areHeroesSpawned = false;
            StartBattle();
        }

        async void OnEnable()
        {
            await UniTask.WaitUntil(() => BattleUIManager.Instance != null);
            BattleUIManager.Instance.OnBattleReady += HandleBattleReady;
            InitWaveData();
        }

        void OnDisable()
        {
            if (BattleUIManager.Instance != null)
                BattleUIManager.Instance.OnBattleReady -= HandleBattleReady;

            foreach (var heroController in _spawnedHeroes)
                if (heroController != null) Destroy(heroController.gameObject);
        }

        private void HandleCharacterDied(CharacterType type)
        {
            OnEnemyKilled?.Invoke(type);
        }

        private void HandleBattleReady(List<FormationSlotSelection> formation)
        {
            ValidateFormationOrThrow(formation);
            _selectedFormation = formation
                .OrderBy(x => x.SlotIndex)
                .Select(x => new FormationSlotSelection(x.Hero, x.SlotIndex))
                .ToList();

            SpawnHeroes(_selectedFormation);

            if (_waveData.CurrentWave % _waveData.TotalWavesBeforeBossAppears == 0)
                SpawnBoss();
            else
                SpawnEnemies();
        }

        void InitWaveData()
        {
            _waveData = new WaveData
            {
                CurrentWave = 1,
                EnemyStats = new HeroStats
                {
                    ATK = 100,
                    CRIT = 10,
                    DEF = 10,
                    Health = 100,
                    MAG = 10,
                    RES = 10,
                    SPD = 20
                },
                BossStats = new HeroStats
                {
                    ATK = 100,
                    CRIT = 20,
                    DEF = 20,
                    Health = 500,
                    MAG = 30,
                    RES = 30,
                    SPD = 40
                },
                TotalWavesBeforeBossAppears = 10,
                AdditionInEachStatPerWave = 10
            };
        }

        static void ValidateFormationOrThrow(IReadOnlyList<FormationSlotSelection> formation)
        {
            if (formation == null || formation.Count != FormationSlotSelection.MaxPartySize)
                throw new InvalidOperationException($"Battle requires exactly {FormationSlotSelection.MaxPartySize} heroes.");

            if (formation.Any(x => x == null || !x.IsValid))
                throw new InvalidOperationException("Battle formation contains an invalid hero or grid slot.");

            if (formation.Select(x => x.SlotIndex).Distinct().Count() != formation.Count)
                throw new InvalidOperationException("Battle formation contains duplicate grid slots.");

            if (formation.Select(x => x.Hero).Distinct().Count() != formation.Count)
                throw new InvalidOperationException("Battle formation contains duplicate heroes.");
        }

        HeroController SpawnCharacter(HeroSO heroSO, Transform spawnTransform, bool isHero, CharacterType type)
        {
            if (heroSO == null) throw new InvalidOperationException("Cannot spawn a null hero.");
            if (spawnTransform == null) throw new InvalidOperationException("Cannot spawn a hero without a spawn transform.");

            var prefab = heroSO.GetHeroControllerPrefab();
            if (prefab == null)
                throw new InvalidOperationException($"Hero '{heroSO.name}' has no HeroController prefab.");

            var newHero = Instantiate(prefab, spawnTransform.position, spawnTransform.rotation);
            newHero.SetHeroData(heroSO, isHero, type);
            newHero.gameObject.name = heroSO.GetHeroProfile().HeroName + "_gameObject";
            newHero.OnDeath.AddListener(HandleCharacterDied);
            _spawnedHeroes.Add(newHero);
            return newHero;
        }

        void SpawnHeroes(IReadOnlyList<FormationSlotSelection> formation)
        {
            if (_heroSpawnTransforms == null || _heroSpawnTransforms.Length != FormationSlotSelection.GridSize)
                throw new InvalidOperationException(
                    $"Battle scene must expose exactly {FormationSlotSelection.GridSize} player formation spawn transforms. Found {_heroSpawnTransforms?.Length ?? 0}.");

            _readyHeroes = new List<HeroController>(formation.Count);
            foreach (var selection in formation)
                _readyHeroes.Add(SpawnCharacter(selection.Hero, _heroSpawnTransforms[selection.SlotIndex], true, CharacterType.hero));

            _areHeroesSpawned = true;
        }

        [ContextMenu("Test Enemies")]
        void SpawnEnemies()
        {
            var allHeroes = ReusableData.Instance.GetHeroSOCollection().GetAllHeroes();
            int count = Mathf.Min(9, Mathf.Min(_enemySpawnTransforms?.Length ?? 0, allHeroes.Length));
            var selectedHeroes = allHeroes
                .OrderBy(_ => Guid.NewGuid())
                .Take(count)
                .ToList();

            _readyEnemies = new List<HeroController>(selectedHeroes.Count);
            for (int i = 0; i < selectedHeroes.Count; i++)
            {
                var enemy = SpawnCharacter(selectedHeroes[i], _enemySpawnTransforms[i], false, CharacterType.enemy);
                enemy.SetStats(_waveData.EnemyStats);
                _readyEnemies.Add(enemy);
            }

            _areEnemiesSpawned = _readyEnemies.Count > 0;
        }

        void SpawnBoss()
        {
            if (_bossSpawnTransforms == null || _bossSpawnTransforms.Length == 0)
                throw new InvalidOperationException("Battle scene has no boss spawn transform.");

            var hero = ReusableData.Instance.GetHeroSOCollection()
                .GetAllHeroes()
                .OrderBy(_ => Guid.NewGuid())
                .FirstOrDefault();

            var boss = SpawnCharacter(hero, _bossSpawnTransforms[0], false, CharacterType.boss);
            boss.SetStats(_waveData.BossStats);
            boss.SetScale(_waveData);
            _readyEnemies = new List<HeroController> { boss };
            _areEnemiesSpawned = true;
        }

        async void StartBattle()
        {
            await UniTask.WaitUntil(() => _areEnemiesSpawned && _areHeroesSpawned);

            ActivateFrontLine(_readyHeroes, FormationSlotSelection.MaxPartySize);
            ActivateFrontLine(_readyEnemies, Mathf.Min(_totalActiveHeroesAtATime, FormationSlotSelection.MaxPartySize));

            var activeHeroes = _readyHeroes.Where(hero => hero != null && hero.IsActive && !hero.IsDead).ToList();
            var activeEnemies = _readyEnemies.Where(hero => hero != null && hero.IsActive && !hero.IsDead).ToList();

            while (activeHeroes.Count > 0 && activeEnemies.Count > 0)
            {
                var attackingHero = activeHeroes[UnityEngine.Random.Range(0, activeHeroes.Count)];
                var targetEnemy = activeEnemies[UnityEngine.Random.Range(0, activeEnemies.Count)];

                attackingHero.SetSpriteRendererState(true);
                targetEnemy.SetSpriteRendererState(true);
                await attackingHero.StartAttack(new AttackInfo
                {
                    TargetCharacter = targetEnemy,
                    AttackerStats = attackingHero.GetHeroSO().GetHeroProfile().Stats,
                    ReceiverStats = targetEnemy.GetEnemyStats()
                });
                attackingHero.SetSpriteRendererState(false);
                targetEnemy.SetSpriteRendererState(false);

                if (targetEnemy.IsDead)
                    await ActivateNewCharacterInLine(_readyEnemies, activeEnemies);

                activeHeroes.RemoveAll(x => x == null || x.IsDead);
                activeEnemies.RemoveAll(x => x == null || x.IsDead);
                if (activeHeroes.Count == 0 || activeEnemies.Count == 0) break;

                await UniTask.WaitForSeconds(UnityEngine.Random.Range(.5f, 1.0f));

                var attackingEnemy = activeEnemies[UnityEngine.Random.Range(0, activeEnemies.Count)];
                var targetHero = activeHeroes[UnityEngine.Random.Range(0, activeHeroes.Count)];

                attackingEnemy.SetSpriteRendererState(true);
                targetHero.SetSpriteRendererState(true);
                await attackingEnemy.StartAttack(new AttackInfo
                {
                    TargetCharacter = targetHero,
                    AttackerStats = attackingEnemy.GetEnemyStats(),
                    ReceiverStats = targetHero.GetHeroSO().GetHeroProfile().Stats
                });
                attackingEnemy.SetSpriteRendererState(false);
                targetHero.SetSpriteRendererState(false);

                if (targetHero.IsDead)
                    await ActivateNewCharacterInLine(_readyHeroes, activeHeroes);

                activeHeroes.RemoveAll(x => x == null || x.IsDead);
                activeEnemies.RemoveAll(x => x == null || x.IsDead);
            }

            OnWaveCompleted?.Invoke(_waveData);

            if (HasAnyTeamDied() == Teams.hero)
                return;

            _waveData.CurrentWave++;
            RestartBattle();
        }

        static void ActivateFrontLine(List<HeroController> ready, int count)
        {
            int activated = 0;
            foreach (var character in ready)
            {
                if (character == null || character.IsDead) continue;
                character.SetActiveState(activated < count);
                activated++;
            }
        }

        void RestartBattle()
        {
            foreach (var enemy in _readyEnemies) if (enemy != null) Destroy(enemy.gameObject);
            foreach (var hero in _readyHeroes) if (hero != null) Destroy(hero.gameObject);

            _readyEnemies.Clear();
            _readyHeroes.Clear();
            _spawnedHeroes.RemoveAll(x => x == null);

            _areHeroesSpawned = false;
            _areEnemiesSpawned = false;

            Gameplay.IncreaseStats(_waveData.EnemyStats, _waveData.AdditionInEachStatPerWave);
            OnWaveStarted?.Invoke(_waveData);
            HandleBattleReady(_selectedFormation);
            StartBattle();
        }

        async Task<bool> ActivateNewCharacterInLine(List<HeroController> readyCharacters, List<HeroController> activeCharacters)
        {
            var deadCharacter = activeCharacters.FirstOrDefault(c => c != null && c.IsDead);
            if (deadCharacter == null) return false;

            var newReadyCharacter = readyCharacters.FirstOrDefault(c => c != null && !c.IsDead && !activeCharacters.Contains(c));

            float duration = 0.5f;
            float timer = 0f;
            var deadStart = deadCharacter.transform.position;
            var deadTarget = _deadCharactersTransform.position;

            while (timer <= duration)
            {
                float t = Mathf.SmoothStep(0, 1, timer / duration);
                deadCharacter.transform.position = Vector2.Lerp(deadStart, deadTarget, t);
                timer += Time.deltaTime;
                await UniTask.Yield();
            }

            deadCharacter.transform.position = deadTarget;
            activeCharacters.Remove(deadCharacter);
            deadCharacter.SetActiveState(false);

            if (newReadyCharacter == null) return false;

            activeCharacters.Add(newReadyCharacter);
            newReadyCharacter.SetActiveState(true);
            return true;
        }

        Teams HasAnyTeamDied()
        {
            if (_readyHeroes.Count > 0 && _readyHeroes.All(hero => hero == null || hero.IsDead))
                return Teams.hero;

            if (_readyEnemies.Count > 0 && _readyEnemies.All(enemy => enemy == null || enemy.IsDead))
                return Teams.enemy;

            return Teams.NULL;
        }
    }
}
