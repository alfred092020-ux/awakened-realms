using AwakenedRealm.Enums;
using UnityEngine;

namespace AwakenedRealm.Scriptables
{
    [CreateAssetMenu(fileName = "Ticket", menuName = "Scriptables/Ticket/New Ticket")]
    public class TicketSO : ScriptableObject
    {
        [SerializeField] TicketType _ticketType;
        public TicketType GetTicketType() => _ticketType;
        [SerializeField] Sprite _ticketSprite;
        public Sprite GetTicketSprite() => _ticketSprite;
    }

}