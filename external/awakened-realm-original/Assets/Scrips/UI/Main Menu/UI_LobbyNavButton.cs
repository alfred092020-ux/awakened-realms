using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    /// <summary>
    /// Lobby destination button. Entries marked "coming soon" stay visible but
    /// non-interactable: no fake navigation is wired for unbuilt destinations.
    /// </summary>
    public class UI_LobbyNavButton : MonoBehaviour
    {
        [SerializeField] private Button _button;
        [SerializeField] private Graphic _icon;
        [SerializeField] private TMP_Text _label;
        [SerializeField] private TMP_Text _badge;
        [SerializeField] private string _badgeText = "SOON";
        [SerializeField] private bool _comingSoon;
        [SerializeField] private CanvasGroup _canvasGroup;

        private void Awake()
        {
            if (_button == null) _button = GetComponent<Button>();
            if (_canvasGroup == null) _canvasGroup = GetComponent<CanvasGroup>();
            ApplyState();
        }

#if UNITY_EDITOR
        private void OnValidate() { ApplyState(); }
#endif

        public bool IsComingSoon => _comingSoon;

        /// <summary>Underlying Unity button the rail hooks for navigation.</summary>
        public Button Button => _button;

        public void SetBadge(string text)
        {
            _badgeText = text;
            ApplyState();
        }

        private void ApplyState()
        {
            if (_badge != null)
            {
                _badge.gameObject.SetActive(_comingSoon);
                _badge.text = _badgeText;
            }
            if (_button != null) _button.interactable = !_comingSoon;
            if (_canvasGroup != null) _canvasGroup.alpha = _comingSoon ? 0.45f : 1f;
            else if (_icon != null)
            {
                Color c = _icon.color;
                c.a = _comingSoon ? 0.45f : 1f;
                _icon.color = c;
            }
        }
    }
}
