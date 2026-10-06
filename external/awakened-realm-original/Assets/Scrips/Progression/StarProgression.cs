using System;
using System.Collections.Generic;
using AwakenedRealm.Enums;

namespace AwakenedRealm.Progression
{
    [Serializable]
    public sealed class StarUpRequirement
    {
        public int CurrentStars;
        public int NextStars;
        public int DuplicateCopies;
        public int Fodder;

        public StarUpRequirement(int currentStars, int nextStars, int duplicateCopies, int fodder)
        {
            CurrentStars = currentStars;
            NextStars = nextStars;
            DuplicateCopies = duplicateCopies;
            Fodder = fodder;
        }
    }

    [Serializable]
    public sealed class OwnedHeroProgression
    {
        public string HeroId;
        public HeroRarity Rarity;
        public int Level = 1;
        public int Stars;
        public int DuplicateCopies;
        public int Fodder;

        public OwnedHeroProgression() { }

        public OwnedHeroProgression(string heroId, HeroRarity rarity, int level = 1)
        {
            if (string.IsNullOrWhiteSpace(heroId))
                throw new ArgumentException("Hero ID is required.", nameof(heroId));

            HeroId = heroId;
            Rarity = rarity;
            Level = Math.Max(1, level);
            Stars = StarProgressionRules.StartingStars(rarity);
        }

        public bool TryStarUp()
        {
            return StarProgressionRules.TryStarUp(this);
        }
    }

    public static class StarProgressionRules
    {
        static readonly Dictionary<HeroRarity, StarUpRequirement[]> Requirements =
            new Dictionary<HeroRarity, StarUpRequirement[]>
            {
                {
                    HeroRarity.rare,
                    new[]
                    {
                        new StarUpRequirement(3, 4, 1, 2),
                        new StarUpRequirement(4, 5, 2, 4)
                    }
                },
                {
                    HeroRarity.epic,
                    new[]
                    {
                        new StarUpRequirement(4, 5, 1, 3),
                        new StarUpRequirement(5, 6, 1, 5),
                        new StarUpRequirement(6, 7, 2, 8),
                        new StarUpRequirement(7, 8, 2, 12)
                    }
                },
                {
                    HeroRarity.legendary,
                    new[]
                    {
                        new StarUpRequirement(5, 6, 1, 5),
                        new StarUpRequirement(6, 7, 1, 8),
                        new StarUpRequirement(7, 8, 2, 12),
                        new StarUpRequirement(8, 9, 2, 18),
                        new StarUpRequirement(9, 10, 3, 25),
                        new StarUpRequirement(10, 11, 4, 35)
                    }
                },
                {
                    HeroRarity.mythic,
                    new[]
                    {
                        new StarUpRequirement(6, 7, 1, 8),
                        new StarUpRequirement(7, 8, 1, 12),
                        new StarUpRequirement(8, 9, 2, 18),
                        new StarUpRequirement(9, 10, 2, 25),
                        new StarUpRequirement(10, 11, 3, 35),
                        new StarUpRequirement(11, 12, 3, 48),
                        new StarUpRequirement(12, 13, 4, 64),
                        new StarUpRequirement(13, 14, 5, 85),
                        new StarUpRequirement(14, 15, 6, 110)
                    }
                }
            };

        public static int StartingStars(HeroRarity rarity)
        {
            switch (rarity)
            {
                case HeroRarity.rare: return 3;
                case HeroRarity.epic: return 4;
                case HeroRarity.legendary: return 5;
                case HeroRarity.mythic: return 6;
                default: throw new ArgumentOutOfRangeException(nameof(rarity), rarity, "Unsupported playable rarity.");
            }
        }

        public static int MaxStars(HeroRarity rarity)
        {
            switch (rarity)
            {
                case HeroRarity.rare: return 5;
                case HeroRarity.epic: return 8;
                case HeroRarity.legendary: return 11;
                case HeroRarity.mythic: return 15;
                default: throw new ArgumentOutOfRangeException(nameof(rarity), rarity, "Unsupported playable rarity.");
            }
        }

        public static StarUpRequirement NextRequirement(HeroRarity rarity, int currentStars)
        {
            int min = StartingStars(rarity);
            int max = MaxStars(rarity);
            if (currentStars < min || currentStars > max)
                throw new ArgumentOutOfRangeException(nameof(currentStars), currentStars, "Star count is outside the rarity range.");
            if (currentStars == max)
                return null;

            StarUpRequirement[] table = Requirements[rarity];
            for (int i = 0; i < table.Length; i++)
                if (table[i].CurrentStars == currentStars)
                    return table[i];

            throw new InvalidOperationException("Missing star-up requirement.");
        }

        public static bool IsMajorEvolutionMilestone(HeroRarity rarity, int stars)
        {
            if (rarity == HeroRarity.legendary)
                return stars == 8 || stars == 11;
            if (rarity == HeroRarity.mythic)
                return stars == 8 || stars == 11 || stars == 13;
            return false;
        }

        public static bool IsApexCompletion(HeroRarity rarity, int stars)
        {
            return rarity == HeroRarity.mythic && stars == 15;
        }

        public static bool TryStarUp(OwnedHeroProgression hero)
        {
            if (hero == null)
                throw new ArgumentNullException(nameof(hero));

            StarUpRequirement requirement = NextRequirement(hero.Rarity, hero.Stars);
            if (requirement == null)
                return false;

            if (hero.DuplicateCopies < requirement.DuplicateCopies || hero.Fodder < requirement.Fodder)
                return false;

            hero.DuplicateCopies -= requirement.DuplicateCopies;
            hero.Fodder -= requirement.Fodder;
            hero.Stars = requirement.NextStars;
            return true;
        }

        public static int ClampStars(HeroRarity rarity, int stars)
        {
            int min = StartingStars(rarity);
            int max = MaxStars(rarity);
            if (stars < min) return min;
            if (stars > max) return max;
            return stars;
        }
    }
}
