using UnityEngine;

namespace AwakenedRealm.UI
{
    /// <summary>
    /// Insets this RectTransform to the device safe area (notch, gesture bar)
    /// in screen space; on devices without a notch it leaves the rect at full
    /// stretch. Apply to full-screen overlay roots.
    /// </summary>
    [RequireComponent(typeof(RectTransform))]
    public class UI_SafeArea : MonoBehaviour
    {
        private RectTransform _rect;
        private Rect _lastSafeArea;
        private bool _isApplying;
        private const float LayoutEpsilon = 0.0001f;

        private void Awake()
        {
            _rect = GetComponent<RectTransform>();
        }

        private void OnEnable() => Apply();

        private void OnRectTransformDimensionsChange()
        {
            if (!_isApplying) Apply();
        }

        private void Update()
        {
            if (Screen.safeArea != _lastSafeArea) Apply();
        }

        private void Apply()
        {
            if (_isApplying || _rect == null || _rect.parent == null) return;

            _lastSafeArea = Screen.safeArea;
            Rect safe = _lastSafeArea;
            float sw = Screen.width;
            float sh = Screen.height;
            if (sw <= 0f || sh <= 0f) return;

            Vector2 anchorMin = new Vector2(safe.xMin / sw, safe.yMin / sh);
            Vector2 anchorMax = new Vector2(safe.xMax / sw, safe.yMax / sh);

            _isApplying = true;
            try
            {
                if ((_rect.anchorMin - anchorMin).sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.anchorMin = anchorMin;
                if ((_rect.anchorMax - anchorMax).sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.anchorMax = anchorMax;
                if (_rect.offsetMin.sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.offsetMin = Vector2.zero;
                if (_rect.offsetMax.sqrMagnitude > LayoutEpsilon * LayoutEpsilon) _rect.offsetMax = Vector2.zero;
            }
            finally
            {
                _isApplying = false;
            }
        }
    }
}
