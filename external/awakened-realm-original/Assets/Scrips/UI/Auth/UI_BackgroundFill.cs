using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    /// <summary>
    /// Keeps a full-screen background Image covered at any aspect ratio by
    /// letterboxing it (cover mode), scaling its RectTransform to match the
    /// parent aspect relative to the sprite aspect.
    /// </summary>
    [RequireComponent(typeof(RectTransform))]
    public class UI_BackgroundFill : MonoBehaviour
    {
        [SerializeField] private Image _image;
        [SerializeField] private float _fillScale = 1f;

        private RectTransform _rect;
        private Sprite _lastSprite;
        private bool _isApplying;
        private const float LayoutEpsilon = 0.01f;

        private void Awake()
        {
            _rect = GetComponent<RectTransform>();
            if (_image == null) _image = GetComponent<Image>();
        }

        private void OnEnable() => Apply();

        private void OnRectTransformDimensionsChange()
        {
            if (!_isApplying) Apply();
        }

        public void Apply()
        {
            if (_isApplying || _rect == null) return;
            RectTransform parent = _rect.parent as RectTransform;
            if (parent == null) return;

            Sprite sprite = _image != null ? _image.sprite : null;
            if (sprite != null) _lastSprite = sprite;

            Sprite s = _lastSprite;
            if (s == null || s.rect.width <= 0f || s.rect.height <= 0f) return;

            float parentW = parent.rect.width;
            float parentH = parent.rect.height;
            if (parentW <= 0f || parentH <= 0f) return;

            float spriteAspect = s.rect.width / s.rect.height;
            float parentAspect = parentW / parentH;

            float w, h;
            if (parentAspect >= spriteAspect)
            {
                w = parentW;
                h = parentW / spriteAspect;
            }
            else
            {
                h = parentH;
                w = parentH * spriteAspect;
            }

            Vector2 center = new Vector2(0.5f, 0.5f);
            Vector2 targetSize = new Vector2(w, h) * _fillScale;

            _isApplying = true;
            try
            {
                if ((_rect.anchorMin - center).sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.anchorMin = center;
                if ((_rect.anchorMax - center).sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.anchorMax = center;
                if ((_rect.pivot - center).sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.pivot = center;
                if (_rect.anchoredPosition.sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.anchoredPosition = Vector2.zero;
                if ((_rect.sizeDelta - targetSize).sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.sizeDelta = targetSize;
            }
            finally
            {
                _isApplying = false;
            }
        }
    }
}
