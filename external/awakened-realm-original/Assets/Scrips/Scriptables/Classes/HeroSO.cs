using AwakenedRealm.Models;
using UnityEngine;

namespace AwakenedRealm.Scriptables
{
    [CreateAssetMenu(fileName = "Hero", menuName = "Scriptables/Heroes/New Hero")]
    public class HeroSO : ScriptableObject
    {
        [SerializeField] HeroProfile _heroProfile;
        public HeroProfile GetHeroProfile() => _heroProfile;

        [SerializeField] Sprite _heroSprite;
        public Sprite GetHeroSprite() => _heroSprite;

        [SerializeField] HeroController _heroPrefab;
        public HeroController GetHeroControllerPrefab() => _heroPrefab;

        // [SerializeField] RuntimeAnimatorController _runtimeAnimatorController;
        // public RuntimeAnimatorController GetRuntimeAnimatorController() => _runtimeAnimatorController;

        // // An optional thing for immersion, using sprites to use them in UI for animations in character selection screen
        // [SerializeField] Sprite[] _idleAnimationSprites;
        // public Sprite[] GetIdleAnimationSprites() => _idleAnimationSprites;
        // [SerializeField] Sprite[] _attackAnimationSprites;
        // public Sprite[] GetAttackAnimationSprites() => _attackAnimationSprites;


        [ContextMenu("Initialize")]
        void Init()
        {
            // HeroProfile newHeroProfile = new HeroProfile
            //     {
            //         Category = _heroProfile.Category,
            //         Rank = Enums.HeroRank.bronze,
            //         Stats = new HeroStats
            //         {
            //             ATK
            //         }
            //     }
        }
    }

}