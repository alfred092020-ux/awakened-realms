using AwakenedRealm.Models;
using TMPro;
using UnityEngine;

namespace AwakenedRealm.UI
{
    public class UI_Profile : MonoBehaviour
    {
        [SerializeField] TMP_Text _displayNameText;
        [SerializeField] TMP_Text _levelText;


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
    }
}
