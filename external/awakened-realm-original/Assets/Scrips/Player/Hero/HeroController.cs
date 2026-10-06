using System;
using System.Threading.Tasks;
using AwakenedRealm.Enums;
using AwakenedRealm.Interfaces;
using AwakenedRealm.Models;
using AwakenedRealm.Scriptables;
using CraftSome.CrossTouch;
using Cysharp.Threading.Tasks;
using Cysharp.Threading.Tasks.Triggers;
using Unity.VisualScripting.Antlr3.Runtime.Misc;
using UnityEngine;
using UnityEngine.Events;

namespace AwakenedRealm
{
    public class HeroController : MonoBehaviour, IDamageable
    {
        Animator _anim;
        SpriteRenderer _spriteRen;
        HeroSO _heroSO;
        public HeroSO GetHeroSO() => _heroSO;
        bool _canMove = false;
        Vector2 _target;
        public bool IsHero = true;

        [SerializeField] HeroCanvas _heroCanvas;
        public HeroCanvas GetHeroCanvas() => _heroCanvas;


        private static readonly float _speedLimitMultiplier = .25f;  // because we are using stats in 100s so we need to control speed as well


        [Tooltip("Intended for enemies")]
        [SerializeField] HeroStats _stats;

        public HeroStats GetEnemyStats() => _stats;




        /// <summary>
        /// if TRUE then he's no longer in the team
        /// </summary>
        public bool IsDead = false;

        /// <summary>
        /// if TRUE then he can participate in the battle, same goes for the enemy as well
        /// </summary>
        public bool IsActive = false;
        CharacterType _characterType;

        Vector2 _startPos;


        // Actions
        public UnityEvent<CharacterType> OnDeath;


        void OnEnable()
        {
            _anim = GetComponent<Animator>();
            _spriteRen = GetComponent<SpriteRenderer>();
            _startPos = transform.position;

        }



        public void SetHeroData(HeroSO heroSO, bool isHero = true, CharacterType type = CharacterType.hero)
        {
            _heroSO = heroSO;
            IsHero = isHero;
            _characterType = type;
            //SetRuntimeAnimatorController(_heroSO.Gethero());

            if (isHero) if (_spriteRen != null) _spriteRen.flipX = true;

            _heroCanvas.SetHeroName(heroSO.GetHeroProfile().HeroName);
            _heroCanvas.SetHealth(Gameplay.MaxHealth); // full
            _heroCanvas.SetMagicPower(Gameplay.MaxMagic); // full

        }

        /// <summary>
        /// Is dead or not (during the battle of course)
        /// </summary>
        /// <param name="state"></param>
        public void SetDeadState(bool state)
        {
            IsDead = state;
        }


        public void SetStats(HeroStats stats)
        {
            _stats = stats;
            _heroCanvas.SetHealth(stats.Health);
        }


        /// <summary>
        /// Used especially when engaged in battles, so they get more visibility than other idle characters
        /// </summary>

        public void SetSpriteRendererState(bool isEngaged)
        {
            _spriteRen.sortingOrder = isEngaged ? 25 : 1;
        }

        public void SetScale(WaveData _waveData)
        {
            transform.localScale *= _waveData.BossScaleMultiplier;
        }


        /// <summary>
        /// Is active for the battle or not!?
        /// </summary>
        /// <param name="state"></param>
        public void SetActiveState(bool state)
        {
            _startPos = transform.position;  // since the character is now active and might have taken a new place later in the battle
            IsActive = state;
        }
        private void SetRuntimeAnimatorController(RuntimeAnimatorController controller) => _anim.runtimeAnimatorController = controller;

        public async Task StartAttack(AttackInfo attackInfo)
        {
            // Set walking animation
            //_anim.CrossFade("Walk", .1f);

            var stats = _characterType == CharacterType.hero ? _heroSO.GetHeroProfile().Stats : _stats;

            // Set target position
            _target = attackInfo.TargetCharacter.transform.position;
            _canMove = true;

            // Get hero's speed (SPD)
            float moveSpeed = stats.SPD;

            // Calculate distance to target
            float distance = Vector3.Distance(transform.position, _target);

            // Calculate time to move based on speed
            float duration = distance / (moveSpeed * _speedLimitMultiplier);

            // Start moving towards the target
            await MoveToTargetAsync(_target, duration);

            // wait for an attack duration as well
            _anim.CrossFade("Basic", .1f);
            await UniTask.WaitForSeconds(UnityEngine.Random.Range(1.0f, 2.0f));
            ApplyDamage(attackInfo);

            // moving back to default position
            await MoveToTargetAsync(_startPos, duration, 0.0f);


            _anim.CrossFade("Idle", .1f);
        }

        private async Task MoveToTargetAsync(Vector3 targetPos, float duration, float stopDistance = 1.0f)
        {
            // Direction from player to target
            Vector3 direction = (targetPos - transform.position).normalized;

            // Adjusted target (stop before enemy)
            Vector3 adjustedTargetPos = targetPos - direction * stopDistance;

            Vector3 startPos = transform.position;
            float timeElapsed = 0f;

            while (timeElapsed < duration)
            {
                transform.position = Vector3.Lerp(startPos, adjustedTargetPos, timeElapsed / duration);

                await Task.Yield();
                timeElapsed += Time.deltaTime;
            }

            // Snap exactly to adjusted position
            transform.position = adjustedTargetPos;

            _canMove = false;
        }

        void ApplyDamage(AttackInfo attackInfo)
        {
            var stats = _characterType == CharacterType.hero ? _heroSO.GetHeroProfile().Stats : _stats;
            if (stats == _heroSO.GetHeroProfile().Stats) Debug.Log($"Damage applied has ATK of {stats.ATK}");
            else Debug.Log($"Damage receiver has health of {stats.Health}");
            var myDamage = stats.ATK;
            if (attackInfo.TargetCharacter.TryGetComponent<IDamageable>(out var damageable))
            {
                damageable.DoDamage(attackInfo.AttackerStats, attackInfo.ReceiverStats);
            }

        }
        public void DoDamage(HeroStats applierStats, HeroStats receiverStats)
        {
            Debug.Log($"Applier ATK {applierStats.ATK}, receiver current health {_heroCanvas.GetCurrentHealth()}");

            // Apply damage
            _heroCanvas.DecreaseAmount(applierStats.ATK);  // Damage the receiver

            // Check if receiver is dead
            if (_heroCanvas.GetCurrentHealth() <= 0f)
            {
                Debug.Log($"Character: {_heroSO.GetHeroProfile().HeroName} is dead at this attack");
                SetDeadState(true);
                OnDeath?.Invoke(_characterType);
                OnDeath.RemoveAllListeners();
            }
        }






        #region Listeners


        #endregion
    }

}