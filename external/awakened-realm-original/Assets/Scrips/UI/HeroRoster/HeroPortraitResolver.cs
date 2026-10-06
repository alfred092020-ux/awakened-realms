using System;
using System.Collections.Generic;
using UnityEngine;

namespace AwakenedRealm.UI.HeroRoster
{
    /// <summary>
    /// Resolves a portrait sprite for an owned hero. Prefers authored art
    /// whose sprite name matches the hero id or kit display name; falls back
    /// to a generated silhouette so every real hero still renders a
    /// deterministic premium-looking tile without presenting fabricated
    /// data as real stats.
    /// </summary>
    public static class HeroPortraitResolver
    {
        static readonly Dictionary<string, Sprite> Resolved =
            new Dictionary<string, Sprite>(StringComparer.Ordinal);

        static readonly Dictionary<string, Sprite> Generated =
            new Dictionary<string, Sprite>(StringComparer.Ordinal);

        static Sprite[] _allSprites;
        static bool _spritesScanned;

        public static Sprite FindPortrait(string heroId)
        {
            if (string.IsNullOrEmpty(heroId))
                return null;

            Sprite cached;
            if (Resolved.TryGetValue(heroId, out cached))
                return cached;

            Sprite sprite = FindAuthoredPortrait(heroId);
            if (sprite == null)
                sprite = GenerateSilhouette(heroId);

            Resolved[heroId] = sprite;
            return sprite;
        }

        public static void ClearCache()
        {
            foreach (var pair in Resolved)
                TryDestroy(pair.Value);
            foreach (var pair in Generated)
                TryDestroy(pair.Value);
            Resolved.Clear();
            Generated.Clear();
        }

        static void TryDestroy(Sprite sprite)
        {
            if (sprite == null)
                return;
            // Only generated sprites are owned by the resolver; authored
            // catalog/asset sprites must never be destroyed.
            if (sprite.name.StartsWith("gen-portrait-", StringComparison.Ordinal))
            {
                if (sprite.texture != null)
                    UnityEngine.Object.Destroy(sprite.texture);
                UnityEngine.Object.Destroy(sprite);
            }
        }

        // ------------------------------------------------------------------
        // Authored art lookup
        // ------------------------------------------------------------------

        static Sprite FindAuthoredPortrait(string heroId)
        {
            // Match on sprite name against the stable hero id or the kit's
            // display name (e.g. "akira-flamesong" / "Akira Flamesong" both
            // compact to "akiraflamesong"). No mapping table is invented.
            EnsureSpriteScan();

            string compactId = Compact(heroId);
            string compactName = null;
            CombatV2.HeroKit kit;
            if (CombatV2.HeroKitCatalog.TryGet(heroId, out kit))
                compactName = Compact(kit.DisplayName);

            for (int i = 0; i < _allSprites.Length; i++)
            {
                Sprite s = _allSprites[i];
                if (s == null)
                    continue;
                string key = Compact(s.name);
                if (key == compactId || (compactName != null && key == compactName))
                    return s;
            }
            return null;
        }

        static void EnsureSpriteScan()
        {
            if (_spritesScanned)
                return;
            _spritesScanned = true;
            _allSprites = Resources.FindObjectsOfTypeAll<Sprite>();
            if (_allSprites == null)
                _allSprites = new Sprite[0];
        }

        static string Compact(string value)
        {
            var chars = new List<char>(value.Length);
            for (int i = 0; i < value.Length; i++)
                if (char.IsLetterOrDigit(value[i]))
                    chars.Add(char.ToLowerInvariant(value[i]));
            return new string(chars.ToArray());
        }

        // ------------------------------------------------------------------
        // Generated silhouette fallback
        // ------------------------------------------------------------------

        static Sprite GenerateSilhouette(string heroId)
        {
            Sprite cached;
            if (Generated.TryGetValue(heroId, out cached))
                return cached;

            int hash = StableHash(heroId);
            float hue = (hash & 0xFF) / 255f;
            Color baseColor = Color.HSVToRGB(hue, 0.55f, 0.82f);
            Color shade = Color.HSVToRGB(hue, 0.7f, 0.40f);

            const int size = 256;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            var px = new Color32[size * size];

            Vector2 center = new Vector2(size * 0.5f, size * 0.52f);
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x, y), center) / (size * 0.62f);
                    float t = Mathf.Clamp01(d);
                    Color c = Color.Lerp(baseColor, shade, t * t);
                    px[y * size + x] = c;
                }
            }

            // Bust silhouette: head + shoulders carved in dark.
            var silhouette = new Color(0.08f, 0.07f, 0.14f, 1f);
            Vector2 head = new Vector2(size * 0.5f, size * 0.62f);
            float headR = size * 0.16f;
            Vector2 shoulders = new Vector2(size * 0.5f, size * 0.18f);
            float shoulderRx = size * 0.32f, shoulderRy = size * 0.26f;

            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    var p = new Vector2(x, y);
                    bool inHead = Vector2.Distance(p, head) < headR;
                    float sx = (p.x - shoulders.x) / shoulderRx;
                    float sy = (p.y - shoulders.y) / shoulderRy;
                    bool inShoulders = sx * sx + sy * sy < 1f;
                    if (inHead || inShoulders)
                        px[y * size + x] = silhouette;
                }
            }

            tex.SetPixels32(px);
            tex.Apply(false, false);
            tex.name = "gen-portrait-" + heroId;

            var sprite = Sprite.Create(
                tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
            sprite.name = tex.name;
            Generated[heroId] = sprite;
            return sprite;
        }

        static int StableHash(string value)
        {
            unchecked
            {
                int hash = 5381;
                for (int i = 0; i < value.Length; i++)
                    hash = (hash * 33) ^ value[i];
                return hash;
            }
        }
    }
}
