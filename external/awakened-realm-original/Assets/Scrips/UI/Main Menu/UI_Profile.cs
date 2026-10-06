using AwakenedRealm.Models;
using TMPro;
using UnityEngine;

namespace AwakenedRealm.UI
{
    public class UI_Profile : MonoBehaviour
    {
        [SerializeField] TMP_Text _displayNameText;
        [SerializeField] TMP_Text _levelText;

        [Header("Wallet (optional)")]
        [SerializeField] TMP_Text _basicTicketsText;
        [SerializeField] TMP_Text _advanceTicketsText;

        [SerializeField] UI_Slide _slideUI;

        void Start()
        {
            _slideUI.Execute();
        }

        public void SetUI_Profile(PlayerProfile playerProfile)
        {
            _displayNameText.text = playerProfile.DisplayName;
            _levelText.text = playerProfile.Level;
        }

        public void SetUI_Wallet(PlayerWallet wallet)
        {
            if (wallet == null) return;
            if (_basicTicketsText != null) _basicTicketsText.text = wallet.BasicTickets.ToString();
            if (_advanceTicketsText != null) _advanceTicketsText.text = wallet.AdvanceTickets.ToString();
        }
    }
}
