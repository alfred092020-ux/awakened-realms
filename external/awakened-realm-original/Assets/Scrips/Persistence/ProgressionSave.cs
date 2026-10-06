using System;
using System.Collections.Generic;
using System.Globalization;
using AwakenedRealm.Enums;
using AwakenedRealm.Progression;
using UnityEngine;

namespace AwakenedRealm.Persistence
{
    [Serializable]
    public sealed class ProgressionSaveData
    {
        public int Version;
        public HeroProgressionRecord[] Heroes;
        public int Gold;
        public int Gems;
        public int SummonTickets;
        public int PlayerXp;
        public int HighestClearedStage;
        public int LegendaryPity;
        public int MythicPity;
        // JsonUtility cannot serialize long, so ticks persist as an
        // invariant-culture string; a missing field means "unset" (0 ticks).
        public string LastSeenUtcTicks;
    }

    [Serializable]
    public sealed class HeroProgressionRecord
    {
        public string HeroId;
        public HeroRarity Rarity;
        public int Level;
        public int Stars;
        public int DuplicateCopies;
        public int Fodder;
    }

    public static class ProgressionSave
    {
        public const int CurrentVersion = 3;
        const string PlayerPrefsKey = "awakened_realms_progression_v2";
        const string PlayerPrefsStateKey = "awakened_realms_progression_state_v3";

        public static string Serialize(IEnumerable<OwnedHeroProgression> heroes)
        {
            if (heroes == null)
                throw new ArgumentNullException(nameof(heroes));

            return JsonUtility.ToJson(new ProgressionSaveData
            {
                Version = CurrentVersion,
                Heroes = ToRecordArray(heroes)
            });
        }

        public static List<OwnedHeroProgression> Deserialize(
            string json,
            ICollection<string> allowedHeroIds = null)
        {
            if (string.IsNullOrWhiteSpace(json))
                return new List<OwnedHeroProgression>();

            ProgressionSaveData data = Parse(json);
            return DeserializeHeroes(data, allowedHeroIds);
        }

        /// <summary>Serializes the full metagame state at the current schema version.</summary>
        public static string SerializeState(GameProgressionState state)
        {
            if (state == null)
                throw new ArgumentNullException(nameof(state));
            state.Validate();

            return JsonUtility.ToJson(new ProgressionSaveData
            {
                Version = CurrentVersion,
                Heroes = ToRecordArray(state.Heroes),
                Gold = state.Gold,
                Gems = state.Gems,
                SummonTickets = state.SummonTickets,
                PlayerXp = state.PlayerXp,
                HighestClearedStage = state.HighestClearedStage,
                LegendaryPity = state.LegendaryPity,
                MythicPity = state.MythicPity,
                LastSeenUtcTicks = state.LastSeenUtcTicks
                    .ToString(CultureInfo.InvariantCulture)
            });
        }

        /// <summary>
        /// Deserializes a full metagame state. Payloads from schema versions that
        /// predate the metagame fields load with zeroed resources and an unset
        /// (zero-tick) LastSeenUtc; no currency is ever invented. Hero records
        /// migrate exactly as the hero-only API does.
        /// </summary>
        public static GameProgressionState DeserializeState(
            string json,
            ICollection<string> allowedHeroIds = null)
        {
            var state = new GameProgressionState();
            if (string.IsNullOrWhiteSpace(json))
                return state;

            ProgressionSaveData data = Parse(json);
            state.Heroes = DeserializeHeroes(data, allowedHeroIds);

            if (data.Version >= 3)
            {
                long lastSeenTicks = 0;
                if (!string.IsNullOrEmpty(data.LastSeenUtcTicks) &&
                    (!long.TryParse(data.LastSeenUtcTicks, NumberStyles.Integer,
                         CultureInfo.InvariantCulture, out lastSeenTicks) ||
                     lastSeenTicks < 0))
                {
                    throw new InvalidOperationException("Progression save has an invalid timestamp.");
                }

                state.Gold = data.Gold;
                state.Gems = data.Gems;
                state.SummonTickets = data.SummonTickets;
                state.PlayerXp = data.PlayerXp;
                state.HighestClearedStage = data.HighestClearedStage;
                state.LegendaryPity = data.LegendaryPity;
                state.MythicPity = data.MythicPity;
                state.LastSeenUtcTicks = lastSeenTicks;
            }

            // Covers nonnegative resources, campaign stage validity, pity
            // ranges, stable/duplicate hero IDs, and hero star ranges.
            state.Validate();
            return state;
        }

        public static void Save(IEnumerable<OwnedHeroProgression> heroes)
        {
            PlayerPrefs.SetString(PlayerPrefsKey, Serialize(heroes));
            PlayerPrefs.Save();
        }

        public static List<OwnedHeroProgression> Load(ICollection<string> allowedHeroIds = null)
        {
            string raw = PlayerPrefs.GetString(PlayerPrefsKey, string.Empty);
            return Deserialize(raw, allowedHeroIds);
        }

        public static void SaveState(GameProgressionState state)
        {
            PlayerPrefs.SetString(PlayerPrefsStateKey, SerializeState(state));
            PlayerPrefs.Save();
        }

        public static GameProgressionState LoadState(ICollection<string> allowedHeroIds = null)
        {
            string raw = PlayerPrefs.GetString(PlayerPrefsStateKey, string.Empty);
            return DeserializeState(raw, allowedHeroIds);
        }

        public static List<OwnedHeroProgression> CreateFresh(
            IEnumerable<Tuple<string, HeroRarity, int>> heroes)
        {
            if (heroes == null)
                throw new ArgumentNullException(nameof(heroes));

            var result = new List<OwnedHeroProgression>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (Tuple<string, HeroRarity, int> entry in heroes)
            {
                if (entry == null || string.IsNullOrWhiteSpace(entry.Item1))
                    throw new InvalidOperationException("Fresh progression requires stable hero IDs.");
                if (!seen.Add(entry.Item1))
                    throw new InvalidOperationException("Fresh progression contains duplicate hero ID: " + entry.Item1);

                result.Add(new OwnedHeroProgression(entry.Item1, entry.Item2, entry.Item3));
            }
            return result;
        }

        static ProgressionSaveData Parse(string json)
        {
            ProgressionSaveData data = JsonUtility.FromJson<ProgressionSaveData>(json);
            if (data == null)
                throw new InvalidOperationException("Progression save is empty or malformed.");
            if (data.Version < 0 || data.Version > CurrentVersion)
                throw new InvalidOperationException("Unsupported progression save version: " + data.Version);
            return data;
        }

        static HeroProgressionRecord[] ToRecordArray(IEnumerable<OwnedHeroProgression> heroes)
        {
            var records = new List<HeroProgressionRecord>();
            var seen = new HashSet<string>(StringComparer.Ordinal);

            foreach (OwnedHeroProgression hero in heroes)
            {
                ValidateHero(hero, null);
                if (!seen.Add(hero.HeroId))
                    throw new InvalidOperationException("Duplicate hero ID in progression save: " + hero.HeroId);

                records.Add(ToRecord(hero));
            }

            return records.ToArray();
        }

        static List<OwnedHeroProgression> DeserializeHeroes(
            ProgressionSaveData data,
            ICollection<string> allowedHeroIds)
        {
            HeroProgressionRecord[] records = data.Heroes ?? Array.Empty<HeroProgressionRecord>();
            var result = new List<OwnedHeroProgression>(records.Length);
            var seen = new HashSet<string>(StringComparer.Ordinal);

            for (int i = 0; i < records.Length; i++)
            {
                HeroProgressionRecord record = records[i];
                if (record == null || string.IsNullOrWhiteSpace(record.HeroId))
                    throw new InvalidOperationException("Progression save contains a hero without a stable ID.");
                if (allowedHeroIds != null && !allowedHeroIds.Contains(record.HeroId))
                    throw new InvalidOperationException("Progression save contains an unknown hero ID: " + record.HeroId);
                if (!seen.Add(record.HeroId))
                    throw new InvalidOperationException("Progression save contains duplicate hero ID: " + record.HeroId);

                OwnedHeroProgression hero = FromRecord(record, data.Version);
                ValidateHero(hero, allowedHeroIds);
                result.Add(hero);
            }

            return result;
        }

        static HeroProgressionRecord ToRecord(OwnedHeroProgression hero)
        {
            return new HeroProgressionRecord
            {
                HeroId = hero.HeroId,
                Rarity = hero.Rarity,
                Level = hero.Level,
                Stars = hero.Stars,
                DuplicateCopies = hero.DuplicateCopies,
                Fodder = hero.Fodder
            };
        }

        static OwnedHeroProgression FromRecord(HeroProgressionRecord record, int version)
        {
            int level = Math.Max(1, record.Level);
            var hero = new OwnedHeroProgression(record.HeroId, record.Rarity, level);

            if (version >= 3)
            {
                // Current schema: read fields raw so range validation can
                // reject corrupted star counts and negative resources.
                hero.Stars = record.Stars;
                hero.DuplicateCopies = record.DuplicateCopies;
                hero.Fodder = record.Fodder;
            }
            else if (version >= 2)
            {
                // Version 2 migration keeps its original lenient clamp.
                hero.Stars = StarProgressionRules.ClampStars(record.Rarity, record.Stars);
                hero.DuplicateCopies = Math.Max(0, record.DuplicateCopies);
                hero.Fodder = Math.Max(0, record.Fodder);
            }
            // Version 0/1 data predates star/copy/fodder fields. JsonUtility
            // leaves absent integer fields at zero, so migration starts the hero
            // at its rarity-specific initial star count with no spendable
            // resources.

            return hero;
        }

        static void ValidateHero(OwnedHeroProgression hero, ICollection<string> allowedHeroIds)
        {
            if (hero == null || string.IsNullOrWhiteSpace(hero.HeroId))
                throw new InvalidOperationException("Hero progression requires a stable hero ID.");
            if (allowedHeroIds != null && !allowedHeroIds.Contains(hero.HeroId))
                throw new InvalidOperationException("Unknown hero ID: " + hero.HeroId);
            if (hero.Level < 1)
                throw new InvalidOperationException("Hero level must be at least 1.");
            if (hero.DuplicateCopies < 0 || hero.Fodder < 0)
                throw new InvalidOperationException("Hero progression resources cannot be negative.");

            int min = StarProgressionRules.StartingStars(hero.Rarity);
            int max = StarProgressionRules.MaxStars(hero.Rarity);
            if (hero.Stars < min || hero.Stars > max)
                throw new InvalidOperationException("Hero star count is invalid for rarity.");
        }
    }
}
