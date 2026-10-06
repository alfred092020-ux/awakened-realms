using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI.HeroRoster
{
    /// <summary>
    /// Procedural five-point star sprite used for star rows. Generated once at
    /// runtime (Cinzel carries no star glyphs and shipping a TTF atlas for one
    /// glyph would be worse); lit/unlit tints come from the roster palette.
    /// </summary>
    public static class StarIconFactory
    {
        static Sprite _starSprite;
        static Texture2D _starTexture;

        public static Sprite Star
        {
            get
            {
                EnsureStar();
                return _starSprite;
            }
        }

        public static readonly Color Lit = new Color(0.98f, 0.80f, 0.34f);
        public static readonly Color Unlit = new Color(0.36f, 0.33f, 0.45f, 0.55f);

        /// <summary>Add a star image child; caller sets anchors/offsets.</summary>
        public static Image CreateStarImage(Transform parent, string name, bool lit)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.sprite = Star;
            img.color = lit ? Lit : Unlit;
            img.preserveAspect = true;
            img.raycastTarget = false;
            return img;
        }

        /// <summary>
        /// Lay out a row of <paramref name="max"/> star icons centered in
        /// <paramref name="parent"/>; <paramref name="lit"/> controls how many
        /// are lit from the left.
        /// </summary>
        public static void FillStarRow(Transform parent, int lit, int max,
            float starSize = 30f, float spacing = 4f)
        {
            for (int i = parent.childCount - 1; i >= 0; i--)
                Object.Destroy(parent.GetChild(i).gameObject);

            float total = max * starSize + (max - 1) * spacing;
            float x = -total * 0.5f + starSize * 0.5f;
            for (int i = 0; i < max; i++)
            {
                Image star = CreateStarImage(parent, "Star" + i, i < lit);
                var rt = star.rectTransform;
                rt.anchorMin = new Vector2(0.5f, 0.5f);
                rt.anchorMax = new Vector2(0.5f, 0.5f);
                rt.pivot = new Vector2(0.5f, 0.5f);
                rt.anchoredPosition = new Vector2(x, 0f);
                rt.sizeDelta = new Vector2(starSize, starSize);
                x += starSize + spacing;
            }
        }

        static void EnsureStar()
        {
            if (_starSprite != null)
                return;

            const int size = 64;
            _starTexture = new Texture2D(size, size, TextureFormat.RGBA32, false);
            var px = new Color32[size * size];
            var clear = new Color32(0, 0, 0, 0);

            // Rasterize a five-point star: top vertex up, symmetric about center.
            var cx = size * 0.5f;
            var cy = size * 0.5f;
            float outerR = size * 0.46f;
            float innerR = outerR * 0.42f;
            var verts = new Vector2[10];
            for (int i = 0; i < 10; i++)
            {
                float angle = Mathf.PI * 0.5f + i * Mathf.PI / 5f;
                float r = (i % 2 == 0) ? outerR : innerR;
                verts[i] = new Vector2(cx + Mathf.Cos(angle) * r, cy + Mathf.Sin(angle) * r);
            }

            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    px[y * size + x] = PointInPolygon(new Vector2(x + 0.5f, y + 0.5f), verts)
                        ? new Color32(255, 255, 255, 255)
                        : clear;
                }
            }

            _starTexture.SetPixels32(px);
            _starTexture.Apply(false, false);
            _starTexture.name = "gen-star-icon";
            _starTexture.filterMode = FilterMode.Bilinear;

            _starSprite = Sprite.Create(
                _starTexture, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
            _starSprite.name = "gen-star-icon";
        }

        static bool PointInPolygon(Vector2 p, Vector2[] poly)
        {
            bool inside = false;
            for (int i = 0, j = poly.Length - 1; i < poly.Length; j = i++)
            {
                if ((poly[i].y > p.y) != (poly[j].y > p.y) &&
                    p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)
                    inside = !inside;
            }
            return inside;
        }
    }
}
