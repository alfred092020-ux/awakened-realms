using System;
using System.Collections.Generic;

namespace AwakenedRealm.Progression
{
    [Serializable]
    public sealed class GameProgressionState
    {
        public List<OwnedHeroProgression> Heroes = new List<OwnedHeroProgression>();
        public int Gold;
        public int Gems;
        public int SummonTickets;
        public int PlayerXp;
        public int HighestClearedStage;
        public int LegendaryPity;
        public int MythicPity;
        public long LastSeenUtcTicks;

        public DateTime LastSeenUtc
        {
            get
            {
                if (LastSeenUtcTicks <= 0)
                    return new DateTime(0, DateTimeKind.Utc);
                return new DateTime(LastSeenUtcTicks, DateTimeKind.Utc);
            }
            set { LastSeenUtcTicks = value.ToUniversalTime().Ticks; }
        }

        public OwnedHeroProgression FindHero(string heroId)
        {
            if (string.IsNullOrEmpty(heroId))
                return null;

            for (int i = 0; i < Heroes.Count; i++)
                if (string.Equals(Heroes[i].HeroId, heroId, StringComparison.Ordinal))
                    return Heroes[i];

            return null;
        }

        public int NextCampaignStage
        {
            get
            {
                CampaignStage next = CampaignCatalog.NextStageAfter(HighestClearedStage);
                return next != null ? next.StageId : CampaignCatalog.MaxStage;
            }
        }

        public void Validate()
        {
            if (Heroes == null)
                throw new InvalidOperationException("Hero roster cannot be null.");
            if (Gold < 0 || Gems < 0 || SummonTickets < 0 || PlayerXp < 0)
                throw new InvalidOperationException("Economy balances cannot be negative.");
            if (HighestClearedStage < 0 || HighestClearedStage > CampaignCatalog.MaxStage)
                throw new InvalidOperationException("Campaign progress is outside the catalog.");
            if (HighestClearedStage != 0 && !CampaignCatalog.IsStage(HighestClearedStage))
                throw new InvalidOperationException("Highest cleared stage is not a catalog stage.");
            if (!SummoningService.IsValidLegendaryPity(LegendaryPity))
                throw new InvalidOperationException("Legendary pity is invalid.");
            if (!SummoningService.IsValidMythicPity(MythicPity))
                throw new InvalidOperationException("Mythic pity is invalid.");

            var seen = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < Heroes.Count; i++)
            {
                OwnedHeroProgression hero = Heroes[i];
                if (hero == null || string.IsNullOrWhiteSpace(hero.HeroId))
                    throw new InvalidOperationException("Roster contains a hero without a stable ID.");
                if (!seen.Add(hero.HeroId))
                    throw new InvalidOperationException("Roster contains duplicate hero ID: " + hero.HeroId);
                if (hero.Level < 1 || hero.DuplicateCopies < 0 || hero.Fodder < 0)
                    throw new InvalidOperationException("Hero has invalid progression values: " + hero.HeroId);
                if (hero.Stars < StarProgressionRules.StartingStars(hero.Rarity) ||
                    hero.Stars > StarProgressionRules.MaxStars(hero.Rarity))
                    throw new InvalidOperationException("Hero stars are outside the rarity range: " + hero.HeroId);
            }
        }
    }
}
