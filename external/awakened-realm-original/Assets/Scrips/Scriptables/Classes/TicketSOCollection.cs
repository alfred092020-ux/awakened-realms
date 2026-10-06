using System.Linq;
using AwakenedRealm.Enums;
using UnityEngine;


namespace AwakenedRealm.Scriptables
{
    [CreateAssetMenu(fileName = "Ticket Collection", menuName = "Scriptables/Ticket/New Ticket Collection")]
    public class TicketSOCollection : ScriptableObject
    {
        [SerializeField] TicketSO[] _allTicketSO;
        public TicketSO[] GetAllTickets() => _allTicketSO;
        public TicketSO GetTicketByType(TicketType ticketType) => _allTicketSO.FirstOrDefault(ticket => ticket.GetTicketType() == ticketType);
    }
}