using UnityEngine;

namespace AwakenedRealm.UI
{
    /// <summary>
    /// Lobby navigation rail. Plays the existing slide/fade-up entrance the
    /// same way UI_MainMenuBottom does; buttons are per-entry UI_LobbyNavButton
    /// so unbuilt destinations stay visibly disabled instead of faking
    /// domain behavior.
    /// </summary>
    public class UI_LobbyNavRail : MonoBehaviour
    {
        [SerializeField] private UI_Slide _slideUI;

        private void Start()
        {
            if (_slideUI != null) _slideUI.Execute();
        }
    }
}
