using System;
using System.Collections.Generic;
using System.Linq;
using AwakenedRealm.Models;
using UnityEngine;
using UnityEngine;

namespace AwakenedRealm.Scriptables
{
    [CreateAssetMenu(fileName = "Hero Collection", menuName = "Scriptables/Heroes/New Hero Collection")]
    public class HeroSOCollection : ScriptableObject
    {
        [SerializeField] HeroSO[] _heroesSO;
        public HeroSO[] GetAllHeroes() => _heroesSO;
        public HeroSO GetHeroByName(string heroName) => _heroesSO.FirstOrDefault(hero => hero.GetHeroProfile().HeroName == heroName);
        public HeroSO GetHeroByID(string id) => _heroesSO.FirstOrDefault(hero => hero.GetHeroProfile().HeroID == id);


        /// <summary>
        /// An extension method used to efficiently get hero profiles without using seperate HeroSO again and again
        /// </summary>
        /// <returns></returns>
        public List<HeroProfile> GetAllHeroProfiles()
        {
            List<HeroProfile> heroProfiles = new List<HeroProfile>();

            foreach (var heroSO in _heroesSO)
            {
                heroProfiles.Add(heroSO.GetHeroProfile());
            }

            return heroProfiles;
        }
    }
}