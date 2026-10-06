using AwakenedRealm.Scriptables;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_Ticket : MonoBehaviour
    {
        [SerializeField] Image _basicTicketImg;
        [SerializeField] Image _advanceTicketImg;
        [SerializeField] TMP_Text _basicTicketText;
        [SerializeField] TMP_Text _advanceTicketText;
        public void SetUI_Ticket(TicketSOCollection collection)
        {
            _basicTicketImg.sprite = collection.GetTicketByType(Enums.TicketType.basic).GetTicketSprite();
            _advanceTicketImg.sprite = collection.GetTicketByType(Enums.TicketType.advance).GetTicketSprite();

            _basicTicketText.text = _advanceTicketText.text = "0";
        }

        public void IncreaseBasicTicket(int increment)
        {
            int previousValue = int.Parse(_basicTicketText.text);
            previousValue += increment;
            _basicTicketText.text = previousValue.ToString();
        }

        public void IncreaseAdvanceTicket(int increment)
        {
            int previousValue = int.Parse(_advanceTicketText.text);
            previousValue += increment;
            _advanceTicketText.text = previousValue.ToString();
        }
    }

}