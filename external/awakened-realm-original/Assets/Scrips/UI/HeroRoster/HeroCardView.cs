using System;
using AwakenedRealm.CombatV2;
using AwakenedRealm.Presentation;
using AwakenedRealm.Progression;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI.HeroRoster
{
    /// <summary>
    /// One portrait-first roster card. Built entirely in code so the scene
    /// file carries no prefab wiring; the pool in HeroRosterScreen reuses
    /// instances across filter/sort rebuilds.
    /// </summary>
    public sealed class HeroCardView : MonoBehaviour
    {
        static readonly Color CardIdle = new Color(0.14f, 0.12f, 0.24f, 0.96f);
        static readonly Color CardSelected = new Color(0.28f, 0.24f, 0.14f, 0.98f);
        static readonly Color NamePlate = new Color(0f, 0f, 0f, 0.62f);
        static readonly Color TextPrimary = new Color(0.96f, 0.94f, 0.99f);
        static readonly Color TextMuted = new Color(0.70f, 0.67f, 0.82f);
        static readonly Color Gold = new Color(0.96f, 0.78f, 0.38f);
        static readonly Color SelectionGlow = new Color(0.98f, 0.82f, 0.42f);

        Image _backplate;
        Image _portrait;
        Image _rarityFrame;
        Image _selectionBorder;
        Text _nameText;
        RectTransform _starsRow;
        Text _starsCount;
        Text _levelText;
        Text _roleText;
        Button _button;
        Action<string> _onSelected;

        public string HeroId { get; private set; }

        public static HeroCardView Create(RectTransform parent, Font font, Action<string> onSelected)
        {
            var go = new GameObject("HeroCard", typeof(RectTransform), typeof(HeroCardView));
            go.transform.SetParent(parent, false);
            var card = go.GetComponent<HeroCardView>();
            card.Build(font, onSelected);
            return card;
        }

        void Build(Font font, Action<string> onSelected)
        {
            _onSelected = onSelected;
            var rt = (RectTransform)transform;

            _backplate = NewImage(rt, "Backplate", CardIdle);
            Stretch(_backplate.rectTransform);

            _portrait = NewImage(_backplate.rectTransform, "Portrait", Color.white);
            _portrait.rectTransform.anchorMin = new Vector2(0f, 0.28f);
            _portrait.rectTransform.anchorMax = Vector2.one;
            _portrait.rectTransform.offsetMin = new Vector2(8f, 8f);
            _portrait.rectTransform.offsetMax = new Vector2(-8f, -8f);
            _portrait.preserveAspect = true;
            _portrait.raycastTarget = false;

            _rarityFrame = NewImage(_backplate.rectTransform, "RarityFrame", new Color(1f, 1f, 1f, 0f));
            _rarityFrame.rectTransform.anchorMin = new Vector2(0f, 0.28f);
            _rarityFrame.rectTransform.anchorMax = Vector2.one;
            _rarityFrame.rectTransform.offsetMin = new Vector2(8f, 8f);
            _rarityFrame.rectTransform.offsetMax = new Vector2(-8f, -8f);
            _rarityFrame.raycastTarget = false;

            _selectionBorder = NewImage(rt, "SelectionBorder", new Color(1f, 1f, 1f, 0f));
            Stretch(_selectionBorder.rectTransform);
            _selectionBorder.raycastTarget = false;

            var namePlate = NewImage(_backplate.rectTransform, "NamePlate", NamePlate);
            namePlate.rectTransform.anchorMin = new Vector2(0f, 0f);
            namePlate.rectTransform.anchorMax = new Vector2(1f, 0.28f);
            namePlate.rectTransform.offsetMin = new Vector2(8f, 8f);
            namePlate.rectTransform.offsetMax = new Vector2(-8f, -8f);
            namePlate.raycastTarget = false;

            _nameText = NewText(namePlate.rectTransform, "Name", font,
                "", 30, FontStyle.Bold, TextAnchor.MiddleLeft, TextPrimary);
            _nameText.rectTransform.anchorMin = new Vector2(0f, 0.5f);
            _nameText.rectTransform.anchorMax = new Vector2(1f, 1f);
            _nameText.rectTransform.offsetMin = new Vector2(14f, 0f);
            _nameText.rectTransform.offsetMax = new Vector2(-8f, -2f);

            _levelText = NewText(namePlate.rectTransform, "Level", font,
                "", 26, FontStyle.Normal, TextAnchor.MiddleLeft, TextMuted);
            _levelText.rectTransform.anchorMin = new Vector2(0f, 0f);
            _levelText.rectTransform.anchorMax = new Vector2(0.55f, 0.55f);
            _levelText.rectTransform.offsetMin = new Vector2(14f, 0f);
            _levelText.rectTransform.offsetMax = Vector2.zero;

            _roleText = NewText(namePlate.rectTransform, "Role", font,
                "", 24, FontStyle.Bold, TextAnchor.MiddleRight, RoleColor(HeroRole.Dps));
            _roleText.rectTransform.anchorMin = new Vector2(0.55f, 0f);
            _roleText.rectTransform.anchorMax = new Vector2(1f, 0.55f);
            _roleText.rectTransform.offsetMin = Vector2.zero;
            _roleText.rectTransform.offsetMax = new Vector2(-12f, 0f);

            _starsRow = NewRect(_backplate.rectTransform, "StarsRow");
            _starsRow.anchorMin = new Vector2(0f, 0f);
            _starsRow.anchorMax = new Vector2(1f, 0.10f);
            _starsRow.offsetMin = new Vector2(6f, 4f);
            _starsRow.offsetMax = new Vector2(-6f, 0f);

            _starsCount = NewText(_backplate.rectTransform, "StarsCount", font,
                "", 24, FontStyle.Bold, TextAnchor.MiddleCenter, Gold);
            _starsCount.rectTransform.anchorMin = new Vector2(0f, 0f);
            _starsCount.rectTransform.anchorMax = new Vector2(1f, 0.10f);
            _starsCount.rectTransform.offsetMin = new Vector2(6f, 4f);
            _starsCount.rectTransform.offsetMax = new Vector2(-6f, 0f);

            _button = gameObject.AddComponent<Button>();
            _button.targetGraphic = _backplate;
            var colors = _button.colors;
            colors.highlightedColor = new Color(1.12f, 1.12f, 1.18f);
            colors.pressedColor = new Color(0.85f, 0.85f, 0.95f);
            _button.colors = colors;
            _button.onClick.AddListener(() =>
            {
                if (_onSelected != null && !string.IsNullOrEmpty(HeroId))
                    _onSelected(HeroId);
            });
        }

        public void Bind(OwnedHeroProgression hero, HeroKit kit, bool selected)
        {
            HeroId = hero != null ? hero.HeroId : null;
            if (hero == null)
                return;

            string displayName = kit != null ? kit.DisplayName : hero.HeroId;
            _nameText.text = displayName;
            _levelText.text = "Lv " + hero.Level;
            _roleText.text = kit != null ? RoleLabel(kit.Role) : string.Empty;
            _roleText.color = kit != null ? RoleColor(kit.Role) : TextMuted;

            int max = StarProgressionRules.MaxStars(hero.Rarity);
            if (max <= 8)
            {
                StarIconFactory.FillStarRow(_starsRow, hero.Stars, max, 26f, 2f);
                _starsRow.gameObject.SetActive(true);
                _starsCount.gameObject.SetActive(false);
            }
            else
            {
                // Legendary/mythic caps exceed a legible glyph row; show the
                // real star count instead of a clipped row.
                _starsRow.gameObject.SetActive(false);
                _starsCount.gameObject.SetActive(true);
                _starsCount.text = hero.Stars + "/" + max;
            }

            Sprite portrait = HeroPortraitResolver.FindPortrait(hero.HeroId);
            _portrait.sprite = portrait;
            _portrait.color = portrait != null ? Color.white : new Color(1f, 1f, 1f, 0f);

            Sprite frame = PresentationVisuals.GetRarityFrame(hero.Rarity);
            _rarityFrame.sprite = frame;
            _rarityFrame.color = frame != null ? Color.white : new Color(1f, 1f, 1f, 0f);

            SetSelected(selected);
        }

        public void SetSelected(bool selected)
        {
            _backplate.color = selected ? CardSelected : CardIdle;
            _selectionBorder.color = selected ? SelectionGlow : new Color(1f, 1f, 1f, 0f);
        }

        static string RoleLabel(HeroRole role)
        {
            switch (role)
            {
                case HeroRole.Dps: return "DPS";
                case HeroRole.Defender: return "DEF";
                case HeroRole.Support: return "SUP";
                default: return role.ToString().ToUpperInvariant();
            }
        }

        static Color RoleColor(HeroRole role)
        {
            switch (role)
            {
                case HeroRole.Dps: return new Color(0.98f, 0.55f, 0.45f);
                case HeroRole.Defender: return new Color(0.50f, 0.78f, 0.98f);
                case HeroRole.Support: return new Color(0.55f, 0.92f, 0.62f);
                default: return TextMuted;
            }
        }

        // ---- tiny UI helpers ------------------------------------------------

        static RectTransform NewRect(Transform parent, string name)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            return (RectTransform)go.transform;
        }

        static Image NewImage(Transform parent, string name, Color color)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = color;
            return img;
        }

        static Text NewText(Transform parent, string name, Font font, string content,
            int size, FontStyle style, TextAnchor anchor, Color color)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Text));
            go.transform.SetParent(parent, false);
            var text = go.GetComponent<Text>();
            text.font = font;
            text.text = content;
            text.fontSize = size;
            text.fontStyle = style;
            text.alignment = anchor;
            text.color = color;
            text.horizontalOverflow = HorizontalWrapMode.Overflow;
            text.verticalOverflow = VerticalWrapMode.Overflow;
            text.raycastTarget = false;
            return text;
        }

        static void Stretch(RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
        }
    }
}
