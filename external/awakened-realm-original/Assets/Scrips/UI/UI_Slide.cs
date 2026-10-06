using UnityEngine;
using DG.Tweening;


namespace AwakenedRealm.UI
{
    public class UI_Slide : MonoBehaviour
    {
        public enum SlideType { topToBottom, bottomToTop, leftToRight, rightToLeft }
        

        [Header("Slide")]
        [SerializeField] private SlideType _slideType = SlideType.topToBottom;
        [SerializeField] private float _duration = 0.35f;
        [SerializeField] private Ease _ease = Ease.OutCubic;

        [Header("Fade (Optional)")]
        [SerializeField] private bool _useFade = true;
        [SerializeField] private float _fadeDuration = 0.25f;

        [Header("Children")]
        [SerializeField] private UI_FadeUp[] _fadeUps;
        [SerializeField] private float _childrenDelay = 0.05f;
        [SerializeField] private bool _disableOnUndoComplete = true;


        [Header("Starting action")]
        [Tooltip("if TRUE then when the game starts the Undo() method will be called")]
        [SerializeField] bool _useUndoOnStart = true;

        private RectTransform _rect;
        private CanvasGroup _canvasGroup;

        private Vector2 _targetPos;
        private Vector2 _offscreenPos;

        private Sequence _sequence;

        private void Awake()
        {
            _rect = GetComponent<RectTransform>();
            _targetPos = _rect.anchoredPosition;

            if (_useFade)
            {
                _canvasGroup = GetComponent<CanvasGroup>();
                if (_canvasGroup == null)
                    _canvasGroup = gameObject.AddComponent<CanvasGroup>();
            }

            CacheOffscreenPosition();
        }

        void Start()
        {
            if (_useUndoOnStart) Undo();
        }

        private void OnRectTransformDimensionsChange()
        {
            CacheOffscreenPosition();
        }

        // -------------------- PUBLIC API --------------------

        [ContextMenu("Execute")]
        public void Execute()
        {
            KillSequence();
            CacheOffscreenPosition();

            gameObject.SetActive(true);

            _rect.anchoredPosition = _offscreenPos;

            if (_useFade && _canvasGroup != null)
            {
                _canvasGroup.alpha = 0f;
                _canvasGroup.blocksRaycasts = true;
                _canvasGroup.interactable = true;
            }

            _sequence = DOTween.Sequence();

            _sequence.Append(
                _rect.DOAnchorPos(_targetPos, _duration).SetEase(_ease)
            );

            if (_useFade && _canvasGroup != null)
            {
                _sequence.Join(
                    _canvasGroup.DOFade(1f, _fadeDuration)
                );
            }

            if (_fadeUps != null && _fadeUps.Length > 0)
            {
                _sequence.InsertCallback(_childrenDelay, () =>
                {
                    for (int i = 0; i < _fadeUps.Length; i++)
                    {
                        if (_fadeUps[i] != null)
                            _fadeUps[i].Execute();
                    }
                });
            }

            _sequence.Play();
        }


        [ContextMenu("Undo")]
        public void Undo()
        {
            KillSequence();
            CacheOffscreenPosition();

            if (_fadeUps != null)
            {
                for (int i = 0; i < _fadeUps.Length; i++)
                {
                    if (_fadeUps[i] != null)
                        _fadeUps[i].Undo();
                }
            }

            _sequence = DOTween.Sequence();

            _sequence.Append(
                _rect.DOAnchorPos(_offscreenPos, _duration).SetEase(Ease.InCubic)
            );

            if (_useFade && _canvasGroup != null)
            {
                _sequence.Join(
                    _canvasGroup.DOFade(0f, _fadeDuration)
                );
            }

            _sequence.OnComplete(() =>
            {
                if (_useFade && _canvasGroup != null)
                {
                    _canvasGroup.blocksRaycasts = false;
                    _canvasGroup.interactable = false;
                }

                if (_disableOnUndoComplete)
                    gameObject.SetActive(false);
            });

            _sequence.Play();
        }

        // -------------------- INTERNAL --------------------

        private void CacheOffscreenPosition()
        {
            if (_rect == null) return;

            Canvas canvas = GetComponentInParent<Canvas>();
            RectTransform canvasRect = canvas ? canvas.GetComponent<RectTransform>() : null;

            float canvasW = canvasRect ? canvasRect.rect.width : Screen.width;
            float canvasH = canvasRect ? canvasRect.rect.height : Screen.height;

            float rectW = _rect.rect.width;
            float rectH = _rect.rect.height;

            float xOffset = canvasW + rectW;
            float yOffset = canvasH + rectH;

            _offscreenPos = _targetPos;

            switch (_slideType)
            {
                case SlideType.topToBottom:
                    _offscreenPos += new Vector2(0f, yOffset);
                    break;
                case SlideType.bottomToTop:
                    _offscreenPos += new Vector2(0f, -yOffset);
                    break;
                case SlideType.leftToRight:
                    _offscreenPos += new Vector2(-xOffset, 0f);
                    break;
                case SlideType.rightToLeft:
                    _offscreenPos += new Vector2(xOffset, 0f);
                    break;
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