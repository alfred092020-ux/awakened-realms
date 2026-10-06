using System.Threading;
using AwakenedRealm.Scriptables;
using Cysharp.Threading.Tasks;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_BattlePlacementGridBlock : MonoBehaviour
    {
        [Tooltip("Legacy scenes use 1..9. SlotIndex exposes the normalized 0..8 value.")]
        public int GridID = 1;

        [SerializeField] Image _ghostImg;
        public Image GetGhostImg() => _ghostImg;
        public bool isGridBlockTaken = false;

        private CancellationTokenSource _cancellationTokenSource;
        HeroSO _heroSO;

        public HeroSO GetHeroSO() => _heroSO;
        public int SlotIndex => Mathf.Clamp(GridID > 0 ? GridID - 1 : GridID, 0, 8);

        void OnEnable()
        {
            RefreshVisual();
        }

        public void SetHeroImage(HeroSO heroSO)
        {
            CancelAnimation();
            _heroSO = heroSO;
            isGridBlockTaken = heroSO != null;
            RefreshVisual();
        }

        public void ClearHero()
        {
            CancelAnimation();
            _heroSO = null;
            isGridBlockTaken = false;
            RefreshVisual();
        }

        void RefreshVisual()
        {
            if (_ghostImg == null) return;
            _ghostImg.enabled = isGridBlockTaken && _heroSO != null;
            _ghostImg.sprite = _heroSO != null ? _heroSO.GetHeroSprite() : null;
        }

        void CancelAnimation()
        {
            if (_cancellationTokenSource == null) return;
            _cancellationTokenSource.Cancel();
            _cancellationTokenSource.Dispose();
            _cancellationTokenSource = null;
        }

        async void AnimatePlacementCharacter(Sprite[] animationSprites, CancellationToken token)
        {
            if (animationSprites == null || animationSprites.Length == 0) return;
            while (!token.IsCancellationRequested)
            {
                foreach (var sprite in animationSprites)
                {
                    if (token.IsCancellationRequested) break;
                    if (_ghostImg != null) _ghostImg.sprite = sprite;
                    await UniTask.WaitForSeconds(0.03f);
                }
            }
        }

        public void DisableImg()
        {
            if (_ghostImg != null) _ghostImg.enabled = false;
        }

        void OnDisable()
        {
            CancelAnimation();
        }
    }
}
