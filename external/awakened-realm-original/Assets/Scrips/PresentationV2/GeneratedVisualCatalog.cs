using System;
using System.Collections.Generic;
using UnityEngine;

namespace AwakenedRealm.Presentation
{
    /// <summary>
    /// Serializable entry type identifier for catalog entries. The key strings remain
    /// stable across the game (e.g. "screen.lobby.day"); this enum is the typed
    /// classification used by validators and callers.
    /// </summary>
    public enum GeneratedVisualKind
    {
        ScreenBackground = 0,
        ChapterBackground = 1,
        BossPortrait = 2,
        EnemyPortrait = 3,
        EquipmentIcon = 4,
        RarityFrame = 5,
        RoleIcon = 6,
        CampaignNodeIcon = 7,
        CurrencyIcon = 8,
        EvolutionAura = 9,
        ProgressionCeremony = 10,
        SummonPortal = 11,
        ConceptEffectSource = 12,
    }

    /// <summary>
    /// Typed, stable lookup for curated generated art. Built by the editor
    /// GeneratedVisualCatalogBuilder and consumed at runtime via PresentationVisuals.
    /// </summary>
    public sealed class GeneratedVisualCatalog : ScriptableObject
    {
        public const string ResourcePath = "AwakenedRealmsGenerated/VisualCatalog";

        [Serializable]
        public sealed class Entry
        {
            public string key;
            public GeneratedVisualKind kind;
            public Sprite sprite;
            public string sourceAssetPath;
            public bool isConceptReferenceOnly;
        }

        [SerializeField] List<Entry> entries = new List<Entry>();

        Dictionary<string, Entry> lookup;

        public IReadOnlyList<Entry> Entries => entries;

        void OnEnable()
        {
            BuildLookup();
        }

        void BuildLookup()
        {
            lookup = new Dictionary<string, Entry>(StringComparer.Ordinal);
            if (entries == null)
            {
                return;
            }

            foreach (var entry in entries)
            {
                if (entry == null || string.IsNullOrEmpty(entry.key))
                {
                    continue;
                }

                // First wins: duplicate keys are a validation failure, but stay
                // deterministic here instead of throwing at resource load time.
                if (!lookup.ContainsKey(entry.key))
                {
                    lookup.Add(entry.key, entry);
                }
            }
        }

        public bool TryGetEntry(string key, out Entry entry)
        {
            if (lookup == null)
            {
                BuildLookup();
            }

            entry = null;
            return !string.IsNullOrEmpty(key) && lookup.TryGetValue(key, out entry);
        }

        public bool TryGetSprite(string key, out Sprite sprite)
        {
            sprite = null;
            if (TryGetEntry(key, out var entry) && entry.sprite != null)
            {
                sprite = entry.sprite;
            }
            return sprite != null;
        }

        /// <summary>Replace all entries. Editor builder use only.</summary>
        public void ReplaceEntries(IEnumerable<Entry> newEntries)
        {
            entries = new List<Entry>(newEntries);
            BuildLookup();
        }
    }
}
