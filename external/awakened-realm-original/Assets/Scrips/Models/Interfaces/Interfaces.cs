using AwakenedRealm.Models;
using AwakenedRealm.Scriptables;
using Unity.VisualScripting.Antlr3.Runtime.Misc;

namespace AwakenedRealm.Interfaces
{
    public interface IDamageable
    {
        /// <summary>
        /// Applies the damage to the opposite party
        /// </summary>
        /// <param name="damageAmount">Attack stat in this game basically</param>
        public void DoDamage(HeroStats applierStats, HeroStats receiverStats);
    }
}