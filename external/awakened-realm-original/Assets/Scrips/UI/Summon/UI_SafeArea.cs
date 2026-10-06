using UnityEngine;

namespace AwakenedRealm.UI.Summon
{
    /// <summary>
    /// Applies the device safe area to this RectTransform's anchors so summon
    /// controls stay clear of notches, punch holes, and home indicators.
    /// </summary>
    [RequireComponent(typeof(RectTransform))]
    public sealed class UI_SafeArea : MonoBehaviour
    {
        RectTransform _rect;
        Rect _lastSafeArea;

        void Awake()
        {
            _rect = GetComponent<RectTransform>();
            Apply();
        }

        void Update()
        {
            if (Screen.safeArea != _lastSafeArea)
                Apply();
        }

        void Apply()
        {
            _lastSafeArea = Screen.safeArea;
            Rect area = _lastSafeArea;

            Vector2 anchorMin = area.position;
            Vector2 anchorMax = area.position + area.size;
            anchorMin.x /= Screen.width;
            anchorMin.y /= Screen.height;
            anchorMax.x /= Screen.width;
            anchorMax.y /= Screen.height;

            _rect.anchorMin = anchorMin;
            _rect.anchorMax = anchorMax;
            _rect.offsetMin = Vector2.zero;
            _rect.offsetMax = Vector2.zero;
        }
    }
}
