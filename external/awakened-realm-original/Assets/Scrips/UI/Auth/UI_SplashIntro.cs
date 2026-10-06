using Cysharp.Threading.Tasks;
using DG.Tweening;
using TMPro;
using UnityEngine;

namespace AwakenedRealm.UI
{
    /// <summary>
    /// Drives the branded intro on the Authentication scene:
    /// Nexus Core Inc. studio splash -> Awakened Realms brand -> sign-in UI.
    /// Purely presentational; auth screens and PlayFab wiring are untouched.
    /// All timers use unscaled time and cancellation is safe on scene unload.
    /// </summary>
    public class UI_SplashIntro : MonoBehaviour
    {
        [Header("Screens")]
        [Tooltip("Sign-in screen; hidden until the intro finishes")]
        [SerializeField] private GameObject _signinScreen;
        [Tooltip("Optional screens to show only after the intro (e.g. SignupScreen)")]
        [SerializeField] private GameObject[] _postIntroScreens;

        [Header("Overlays")]
        [SerializeField] private CanvasGroup _studioSplash;
        [SerializeField] private CanvasGroup _brandSplash;

        [Header("Timing (unscaled seconds)")]
        [SerializeField] private float _splashFadeIn = 0.45f;
        [SerializeField] private float _splashHold = 1.15f;
        [SerializeField] private float _brandFadeIn = 0.6f;
        [SerializeField] private float _brandHold = 1.35f;
        [SerializeField] private float _fadeOut = 0.5f;

        private RectTransform _brandRect;
        private Vector3 _brandScale;
        private bool _finished;

        private void Awake()
        {
            if (_brandSplash != null)
            {
                _brandRect = _brandSplash.GetComponent<RectTransform>();
                if (_brandRect != null) _brandScale = _brandRect.localScale;
            }

            // Sign-in UI stays hidden until the intro completes.
            if (_signinScreen != null) _signinScreen.SetActive(false);

            if (_studioSplash != null)
            {
                _studioSplash.alpha = 0f;
                _studioSplash.gameObject.SetActive(true);
            }
            if (_brandSplash != null)
            {
                _brandSplash.alpha = 0f;
                _brandSplash.gameObject.SetActive(true);
            }
        }

        private void Start()
        {
            RunIntroAsync().Forget();
        }

        private void OnDestroy()
        {
            if (_studioSplash != null) _studioSplash.DOKill();
            if (_brandSplash != null) _brandSplash.DOKill();
            if (_brandRect != null) _brandRect.DOKill();
        }

        private async UniTaskVoid RunIntroAsync()
        {
            var token = this.GetCancellationTokenOnDestroy();

            try
            {
                if (_studioSplash != null)
                {
                    await Fade(_studioSplash, 1f, _splashFadeIn, token);
                    await Wait(_splashHold, token);
                    await Fade(_studioSplash, 0f, _fadeOut, token);
                    _studioSplash.gameObject.SetActive(false);
                }

                if (_brandSplash != null)
                {
                    // Gentle scale-up while the brand fades in for a premium feel.
                    if (_brandRect != null)
                    {
                        _brandRect.localScale = _brandScale * 0.94f;
                        _brandRect.DOScale(_brandScale, _brandFadeIn + _brandHold)
                            .SetEase(Ease.OutCubic).SetUpdate(true);
                    }

                    await Fade(_brandSplash, 1f, _brandFadeIn, token);
                    await Wait(_brandHold, token);
                    await Fade(_brandSplash, 0f, _fadeOut, token);
                    _brandSplash.gameObject.SetActive(false);
                }
            }
            catch (System.OperationCanceledException)
            {
                // Scene unloaded mid-intro; nothing else to do.
                return;
            }

            Finish();
        }

        /// <summary>Skips straight to the auth UI (callable from taps if desired).</summary>
        public void Finish()
        {
            if (_finished) return;
            _finished = true;

            if (_studioSplash != null) _studioSplash.gameObject.SetActive(false);
            if (_brandSplash != null) _brandSplash.gameObject.SetActive(false);

            if (_postIntroScreens != null)
            {
                foreach (var screen in _postIntroScreens)
                {
                    if (screen != null) screen.SetActive(true);
                }
            }

            if (_signinScreen != null) _signinScreen.SetActive(true);
        }

        private static async UniTask Fade(CanvasGroup group, float target, float duration,
            System.Threading.CancellationToken token)
        {
            if (duration <= 0f)
            {
                group.alpha = target;
                return;
            }

            Tween tween = group.DOFade(target, duration).SetEase(Ease.InOutSine).SetUpdate(true);
            while (tween.IsActive() && tween.IsPlaying())
            {
                token.ThrowIfCancellationRequested();
                await UniTask.Yield(PlayerLoopTiming.Update, token);
            }
        }

        private static UniTask Wait(float seconds, System.Threading.CancellationToken token)
        {
            if (seconds <= 0f) return UniTask.CompletedTask;
            return UniTask.WaitForSeconds(seconds, ignoreTimeScale: true,
                cancellationToken: token);
        }
    }
}
