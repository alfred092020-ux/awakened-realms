using System;
using System.Collections.Generic;
using UnityEngine;

namespace AwakenedRealm.Presentation
{
    /// <summary>
    /// Maps curated concept-FX source art to stable semantic effect IDs. Concept PNGs are
    /// source references; entries flagged RequiresRuntimeRebuild must be recreated as
    /// particles/trails/shaders/pooled VFX before they are considered final.
    /// </summary>
    public sealed class GeneratedEffectCatalog : ScriptableObject
    {
        public const string ResourcePath = "AwakenedRealmsGenerated/EffectCatalog";

        [Serializable]
        public sealed class EffectEntry
        {
            public string effectId;
            public string faction;
            public Sprite sourceSprite;
            public string sourceAssetPath;
            public bool requiresRuntimeRebuild;
        }

        [SerializeField] List<EffectEntry> effects = new List<EffectEntry>();

        Dictionary<string, EffectEntry> lookup;

        public IReadOnlyList<EffectEntry> Effects => effects;

        void OnEnable()
        {
            BuildLookup();
        }

        void BuildLookup()
        {
            lookup = new Dictionary<string, EffectEntry>(StringComparer.Ordinal);
            if (effects == null)
            {
                return;
            }

            foreach (var effect in effects)
            {
                if (effect == null || string.IsNullOrEmpty(effect.effectId))
                {
                    continue;
                }

                if (!lookup.ContainsKey(effect.effectId))
                {
                    lookup.Add(effect.effectId, effect);
                }
            }
        }

        public bool TryGetEffect(string effectId, out EffectEntry effect)
        {
            if (lookup == null)
            {
                BuildLookup();
            }

            effect = null;
            return !string.IsNullOrEmpty(effectId) && lookup.TryGetValue(effectId, out effect);
        }

        public void ReplaceEffects(IEnumerable<EffectEntry> newEffects)
        {
            effects = new List<EffectEntry>(newEffects);
            BuildLookup();
        }
    }
}
