using System;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AwakenedRealm.UI
{
    /// <summary>
    /// Lobby navigation rail. Plays the existing slide/fade-up entrance the
    /// same way UI_MainMenuBottom does; buttons are per-entry UI_LobbyNavButton
    /// so unbuilt destinations stay visibly disabled instead of faking
    /// domain behavior.
    ///
    /// Scene names are serialized per destination so only scenes that actually
    /// exist and belong to the product are wired; coming-soon entries keep an
    /// empty scene name and stay non-interactable.
    /// </summary>
    public class UI_LobbyNavRail : MonoBehaviour
    {
        [Serializable]
        private struct NavDestination
        {
            public UI_LobbyNavButton button;
            [Tooltip("Scene name as it appears in Build Settings. Leave empty for Coming Soon.")]
            public string sceneName;
        }

        [SerializeField] private UI_Slide _slideUI;
        [SerializeField] private NavDestination[] _destinations;

        private bool _navigatingAway;

        private void Awake()
        {
            if (_destinations == null) return;
            foreach (var dest in _destinations)
            {
                if (dest.button == null || string.IsNullOrEmpty(dest.sceneName)) continue;
                if (dest.button.IsComingSoon) continue;
                string scene = dest.sceneName;
                dest.button.Button?.onClick.AddListener(() => TryNavigate(scene));
            }
        }

        private void Start()
        {
            if (_slideUI != null) _slideUI.Execute();
        }

        private void Update()
        {
            // Android system back surfaces as Escape. The lobby is the root
            // destination, so this is a deliberate no-op: swallowing it here
            // keeps QA from stranding or quitting the session unexpectedly.
            if (Input.GetKeyDown(KeyCode.Escape)) { }
        }

        private void TryNavigate(string sceneName)
        {
            // Latch so double taps (or a tap plus system-back in the same beat)
            // can never enqueue two scene loads.
            if (_navigatingAway) return;

            if (!Application.CanStreamedLevelBeLoaded(sceneName))
            {
                Debug.LogWarning($"[LobbyNav] Scene '{sceneName}' is not in Build Settings; staying on MainMenu.");
                return;
            }

            _navigatingAway = true;
            SceneManager.LoadScene(sceneName);
        }
    }
}
