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

        private void Awake()
        {
            _rect = GetComponent<RectTransform>();
        }

        private void OnEnable() => Apply();

        private void OnRectTransformDimensionsChange() => Apply();

        private void Update()
        {
            if (Screen.safeArea != _lastSafeArea) Apply();
        }

        private void Apply()
        {
            if (_rect == null || _rect.parent == null) return;

            _lastSafeArea = Screen.safeArea;
            Rect safe = _lastSafeArea;
            float sw = Screen.width;
            float sh = Screen.height;
            if (sw <= 0f || sh <= 0f) return;

            Vector2 anchorMin = new Vector2(safe.xMin / sw, safe.yMin / sh);
            Vector2 anchorMax = new Vector2(safe.xMax / sw, safe.yMax / sh);

            _rect.anchorMin = anchorMin;
            _rect.anchorMax = anchorMax;
            _rect.offsetMin = Vector2.zero;
            _rect.offsetMax = Vector2.zero;
        }
    }
}
