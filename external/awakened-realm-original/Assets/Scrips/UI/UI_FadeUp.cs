using UnityEngine;
using DG.Tweening;

namespace AwakenedRealm.UI
{
    public class UI_FadeUp : MonoBehaviour
    {
        public enum FadeUpType { topToBottom, bottomToTop, leftToRight, rightToLeft }

        [Header("FadeUp")]
        [SerializeField] private FadeUpType _fadeUpType = FadeUpType.bottomToTop;
        [SerializeField] private float _offset = 40f;
        [SerializeField] private float _duration = 0.25f;
        [SerializeField] private float _delay = 0f;
        [SerializeField] private Ease _ease = Ease.OutCubic;

        private RectTransform _rect;
        private CanvasGroup _canvasGroup;

        private Vector2 _originalPos;   // ✅ true original
        private Vector2 _startPos;      // original + offset
        private bool _hasCachedOriginal;

        private Sequence _sequence;

        private void Awake()
        {
            _rect = GetComponent<RectTransform>();

            _canvasGroup = GetComponent<CanvasGroup>();
            if (_canvasGroup == null)
                _canvasGroup = gameObject.AddComponent<CanvasGroup>();

            CacheOriginalPosition();
            CacheStartPosition();
        }

        private void OnEnable()
        {
            // If layout groups/content size fitter modify positions on enable,
            // recache original ONLY if you want that updated baseline.
            // Comment this out if you want original locked forever after Awake.
            CacheOriginalPosition();
            CacheStartPosition();
        }

        private void OnRectTransformDimensionsChange()
        {
            // Only recompute start offset based on the cached original.
            CacheStartPosition();
        }

        // -------------------- PUBLIC API --------------------

        public void Execute()
        {
            KillSequence();
            CacheStartPosition();

            gameObject.SetActive(true);

            _rect.anchoredPosition = _startPos;
            _canvasGroup.alpha = 0f;

            _sequence = DOTween.Sequence();

            if (_delay > 0f)
                _sequence.AppendInterval(_delay);

            _sequence.Append(_rect.DOAnchorPos(_originalPos, _duration).SetEase(_ease));
            _sequence.Join(_canvasGroup.DOFade(1f, _duration));

            _sequence.Play();
        }

        public void Undo()
        {
            KillSequence();
            CacheStartPosition();

            _sequence = DOTween.Sequence();

            if (_delay > 0f)
                _sequence.AppendInterval(_delay);

            _sequence.Append(_rect.DOAnchorPos(_startPos, _duration).SetEase(Ease.InCubic));
            _sequence.Join(_canvasGroup.DOFade(0f, _duration));

            _sequence.Play();
        }

        // Optional helper if you ever want to force it back instantly
        public void SnapToOriginal()
        {
            KillSequence();
            CacheOriginalPosition();
            CacheStartPosition();

            _rect.anchoredPosition = _originalPos;
            _canvasGroup.alpha = 1f;
        }

        // -------------------- INTERNAL --------------------

        private void CacheOriginalPosition()
        {
            if (_rect == null) return;

            // Cache only once unless you WANT it to update when layout changes.
            if (_hasCachedOriginal) return;

            _originalPos = _rect.anchoredPosition;
            _hasCachedOriginal = true;
        }

        private void CacheStartPosition()
        {
            if (_rect == null) return;

            _startPos = _originalPos;

            switch (_fadeUpType)
            {
                case FadeUpType.topToBottom: _startPos += new Vector2(0f, _offset); break;
                case FadeUpType.bottomToTop: _startPos += new Vector2(0f, -_offset); break;
                case FadeUpType.leftToRight: _startPos += new Vector2(-_offset, 0f); break;
                case FadeUpType.rightToLeft: _startPos += new Vector2(_offset, 0f); break;
            }
        }

        private void KillSequence()
        {
            if (_sequence != null)
            {
                _sequence.Kill();
                _sequence = null;
            }

            if (_rect != null) _rect.DOKill();
            if (_canvasGroup != null) _canvasGroup.DOKill();
        }
    }
}
