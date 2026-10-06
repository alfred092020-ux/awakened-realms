using System;
using System.Collections.Generic;
using System.Text;
using AwakenedRealm.EquipmentV2;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace AwakenedRealm.UI.Equipment
{
    /// <summary>
    /// Player-visible EquipmentV2 inventory / loadout / enhancement screen.
    /// Presentation only: no equipment persistence/provider exists yet, so the
    /// screen renders an honest empty/unavailable state and every mutating
    /// action (Equip / Remove / Enhance / Lock) stays disabled. Hero rows come
    /// exclusively from the authoritative progression save — there is no
    /// synthetic roster, no seeded instances, and no funded wallet.
    /// Item artwork is generated concept art keyed by slot + rarity; it is
    /// decorative and never represents item state.
    /// </summary>
    public sealed class EquipmentScreenController : MonoBehaviour
    {
        const string MainMenuSceneName = "MainMenu";
        const float CellSize = 190f;
        const float CellSpacing = 16f;
        const float SlotCellSize = 150f;

        // ---------- Domain state (scene-scoped; no persistence for equipment) ----------
        EquipmentCatalog _catalog;
        EquipmentInventory _inventory;
        EquipmentLoadouts _loadouts;
        readonly List<HeroRef> _heroes = new List<HeroRef>();
        int _heroIndex;
        string _selectedInstanceId;
        EquipmentSlot? _filter;
        bool _busy;
        bool _navigatingAway;

        // ---------- Scene references ----------
        [SerializeField] RectTransform _safeAreaRoot;

        // ---------- Generated art (decorative only) ----------
        [SerializeField] Sprite[] _rarityFrames = new Sprite[4]; // Rare, Epic, Legendary, Mythic
        [SerializeField] Sprite _artWeapon, _artHelmet, _artArmor, _artBoots, _artAccessory, _artRelic;
        [SerializeField] Sprite _goldIcon;
        [SerializeField] Sprite _backdropSprite;
        [SerializeField] Sprite[] _heroPortraits = new Sprite[0];

        // ---------- Runtime UI ----------
        TextMeshProUGUI _goldText, _stonesText, _heroNameText, _powerText, _toastText;
        readonly Dictionary<EquipmentSlot, SlotView> _slotViews = new Dictionary<EquipmentSlot, SlotView>();
        RectTransform _gridContent;
        ScrollRect _gridScroll;
        TextMeshProUGUI _gridEmptyText;
        TextMeshProUGUI _detailName, _detailMeta, _detailStats, _detailSet, _detailStatus;
        Image _detailIcon, _detailFrame;
        Button _equipButton, _unequipButton, _enhanceButton, _lockButton, _backButton;
        Button _prevHeroButton, _nextHeroButton;
        TextMeshProUGUI _equipLabel, _enhanceLabel, _lockLabel;
        RectTransform _setsContent;
        readonly List<TextMeshProUGUI> _chipLabels = new List<TextMeshProUGUI>();
        Image _portraitImage;
        RectTransform _toastRoot;
        float _toastUntil;

        sealed class HeroRef
        {
            public string Id;
            public string Name;
            public Sprite Portrait;
        }

        sealed class SlotView
        {
            public Image Icon;
            public Image Frame;
            public TextMeshProUGUI Level;
        }

        // ------------------------------------------------------------------
        // Setup
        // ------------------------------------------------------------------
        void Awake()
        {
            // The catalog provides presentation metadata only (names, rarity,
            // slot, stats). Nothing is ever added to the inventory or wallet —
            // no production equipment persistence/provider exists yet.
            _catalog = EquipmentCatalog.CreateDefault();
            _inventory = new EquipmentInventory();
            _loadouts = new EquipmentLoadouts();
            ResolveHeroes();
        }

        void ResolveHeroes()
        {
            // Hero identity comes only from the authoritative progression
            // save. A missing/corrupt save yields zero heroes — the screen
            // shows an unavailable state instead of pretending ownership.
            AwakenedRealm.Progression.GameProgressionState state = null;
            try { state = AwakenedRealm.Persistence.ProgressionSave.LoadState(); }
            catch (Exception) { state = null; }

            if (state != null && state.Heroes != null && state.Heroes.Count > 0)
            {
                for (int i = 0; i < state.Heroes.Count; i++)
                {
                    var h = state.Heroes[i];
                    if (h == null || string.IsNullOrEmpty(h.HeroId))
                        continue;
                    _heroes.Add(new HeroRef { Id = h.HeroId, Name = h.HeroId, Portrait = PortraitFor(i) });
                }
            }
        }

        Sprite PortraitFor(int index)
        {
            return _heroPortraits != null && _heroPortraits.Length > 0
                ? _heroPortraits[index % _heroPortraits.Length]
                : null;
        }

        string CurrentHeroId
        {
            get { return _heroes.Count > 0 ? _heroes[Mathf.Clamp(_heroIndex, 0, _heroes.Count - 1)].Id : null; }
        }

        // ------------------------------------------------------------------
        // UI construction
        // ------------------------------------------------------------------
        void Start()
        {
            BuildUI();
            SelectItem(null);
            RefreshAll();
        }

        void Update()
        {
            if (_toastRoot != null && _toastRoot.gameObject.activeSelf && Time.unscaledTime > _toastUntil)
                _toastRoot.gameObject.SetActive(false);

            // Android system-back surfaces as Escape; route it through the same
            // guarded return path as the on-screen Back button.
            if (Input.GetKeyDown(KeyCode.Escape))
                OnBack();
        }

        void BuildUI()
        {
            RectTransform root = _safeAreaRoot;
            if (root == null)
            {
                root = NewRect("SafeArea", transform);
                _safeAreaRoot = root;
            }
            var self = transform as RectTransform;
            if (self != null) Stretch(self, 0, 0, 0, 0);
            ApplySafeArea(root);

            BuildBackdrop(root);
            BuildHeader(root);
            BuildLoadoutPanel(root);
            BuildSetsPanel(root);
            BuildGridPanel(root);
            BuildDetailPanel(root);
            BuildToast(root);
            LayoutForPortrait(root);
        }

        /// <summary>Mirrors Screen.safeArea into the root rect so notches and
        /// gesture bars never cover tappable UI.</summary>
        static void ApplySafeArea(RectTransform rt)
        {
            Rect safe = Screen.safeArea;
            Vector2 size = new Vector2(Mathf.Max(1f, Screen.width), Mathf.Max(1f, Screen.height));
            Vector2 min = new Vector2(safe.xMin / size.x, safe.yMin / size.y);
            Vector2 max = new Vector2(safe.xMax / size.x, safe.yMax / size.y);
            rt.anchorMin = min;
            rt.anchorMax = max;
            rt.offsetMin = rt.offsetMax = Vector2.zero;
        }

        static RectTransform NewRect(string name, Transform parent)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            return rt;
        }

        Image NewImage(string name, Transform parent, Color color, Sprite sprite = null)
        {
            Image img = NewRect(name, parent).gameObject.AddComponent<Image>();
            img.color = color;
            img.sprite = sprite;
            img.raycastTarget = false;
            return img;
        }

        TextMeshProUGUI NewText(string name, Transform parent, string text, float size,
            Color color, TextAlignmentOptions align = TextAlignmentOptions.Left, FontStyles style = FontStyles.Normal)
        {
            var tmp = NewRect(name, parent).gameObject.AddComponent<TextMeshProUGUI>();
            tmp.text = text;
            tmp.fontSize = size;
            tmp.color = color;
            tmp.alignment = align;
            tmp.fontStyle = style;
            tmp.raycastTarget = false;
            tmp.textWrappingMode = TextWrappingModes.Normal;
            return tmp;
        }

        static void Stretch(RectTransform rt, float l, float t, float r, float b)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(l, b);
            rt.offsetMax = new Vector2(-r, -t);
        }

        static void Anchor(RectTransform rt, float ax, float ay, float w, float h, float px, float py)
        {
            rt.anchorMin = rt.anchorMax = new Vector2(ax, ay);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(w, h);
            rt.anchoredPosition = new Vector2(px, py);
        }

        Button NewButton(string name, Transform parent, Color bg, UnityEngine.Events.UnityAction onClick)
        {
            Image img = NewImage(name, parent, bg);
            img.raycastTarget = true;
            var btn = img.gameObject.AddComponent<Button>();
            btn.targetGraphic = img;
            var colors = btn.colors;
            colors.highlightedColor = new Color(1f, 1f, 1f, 1f);
            colors.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f);
            colors.fadeDuration = 0.06f;
            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            return btn;
        }

        // ---------- Palette ----------
        static readonly Color Panel = new Color(0.10f, 0.12f, 0.20f, 0.94f);
        static readonly Color PanelSoft = new Color(0.16f, 0.19f, 0.30f, 0.95f);
        static readonly Color Gold = new Color(0.94f, 0.76f, 0.31f, 1f);
        static readonly Color Ink = new Color(0.92f, 0.93f, 0.98f, 1f);
        static readonly Color Muted = new Color(0.62f, 0.65f, 0.75f, 1f);
        static readonly Color Accent = new Color(0.45f, 0.72f, 1f, 1f);
        static readonly Color Good = new Color(0.42f, 0.85f, 0.55f, 1f);
        static readonly Color Bad = new Color(1f, 0.47f, 0.42f, 1f);

        static readonly Color[] RarityColors =
        {
            new Color(0.45f, 0.68f, 1.00f, 1f), // Rare
            new Color(0.72f, 0.47f, 1.00f, 1f), // Epic
            new Color(1.00f, 0.68f, 0.25f, 1f), // Legendary
            new Color(1.00f, 0.40f, 0.55f, 1f), // Mythic
        };

        static readonly string[] RarityNames = { "Rare", "Epic", "Legendary", "Mythic" };
        static readonly string[] SlotNames = { "Weapon", "Helmet", "Armor", "Boots", "Accessory", "Relic" };

        void BuildBackdrop(RectTransform root)
        {
            Image bg = NewImage("Backdrop", root, new Color(0.5f, 0.55f, 0.7f, 1f), _backdropSprite);
            Stretch((RectTransform)bg.transform, 0, 0, 0, 0);

            Image shade = NewImage("Shade", root, new Color(0.03f, 0.04f, 0.09f, 0.90f));
            Stretch((RectTransform)shade.transform, 0, 0, 0, 0);

            Image glowTop = NewImage("GlowTop", root, new Color(0.18f, 0.30f, 0.55f, 0.16f));
            RectTransform gt = (RectTransform)glowTop.transform;
            gt.anchorMin = new Vector2(0, 0.62f); gt.anchorMax = new Vector2(1, 1);
            gt.offsetMin = gt.offsetMax = Vector2.zero;

            Image glowBottom = NewImage("GlowBottom", root, new Color(0.45f, 0.20f, 0.40f, 0.10f));
            RectTransform gb = (RectTransform)glowBottom.transform;
            gb.anchorMin = new Vector2(0, 0); gb.anchorMax = new Vector2(1, 0.34f);
            gb.offsetMin = gb.offsetMax = Vector2.zero;
        }

        void BuildHeader(RectTransform root)
        {
            RectTransform header = NewRect("Header", root);
            header.anchorMin = new Vector2(0, 1); header.anchorMax = new Vector2(1, 1);
            header.pivot = new Vector2(0.5f, 1);
            header.sizeDelta = new Vector2(0, 168);
            header.anchoredPosition = Vector2.zero;

            Image strip = NewImage("HeaderStrip", header, new Color(0.06f, 0.08f, 0.15f, 0.85f));
            Stretch((RectTransform)strip.transform, 0, 0, 0, 0);

            _backButton = NewButton("BackButton", header, PanelSoft, OnBack);
            Anchor((RectTransform)_backButton.transform, 0, 0.5f, 150, 84, 100, 0);
            NewText("BackLabel", _backButton.transform, "< BACK", 30, Ink, TextAlignmentOptions.Center, FontStyles.Bold)
                .rectTransform.StretchFill();

            TextMeshProUGUI title = NewText("Title", header, "EQUIPMENT", 46, Gold,
                TextAlignmentOptions.Center, FontStyles.Bold);
            Anchor((RectTransform)title.transform, 0.5f, 0.5f, 560, 90, 0, 0);
            title.characterSpacing = 14;

            RectTransform wallet = NewRect("Wallet", header);
            Anchor(wallet, 1, 0.5f, 380, 76, -205, 0);

            Image goldChip = NewImage("GoldChip", wallet, PanelSoft);
            Anchor((RectTransform)goldChip.transform, 0, 0.5f, 180, 64, 90, 0);
            if (_goldIcon != null)
            {
                Image goldIco = NewImage("GoldIcon", goldChip.transform, Color.white, _goldIcon);
                Anchor((RectTransform)goldIco.transform, 0, 0.5f, 40, 40, 30, 0);
            }
            _goldText = NewText("GoldText", goldChip.transform, "0", 28, Gold, TextAlignmentOptions.Left, FontStyles.Bold);
            Anchor((RectTransform)_goldText.transform, 0, 0.5f, 120, 54, 95, 0);

            Image stoneChip = NewImage("StoneChip", wallet, PanelSoft);
            Anchor((RectTransform)stoneChip.transform, 1, 0.5f, 180, 64, -90, 0);
            TextMeshProUGUI stoneIco = NewText("StoneIcon", stoneChip.transform, "+", 40, Accent,
                TextAlignmentOptions.Center, FontStyles.Bold);
            Anchor((RectTransform)stoneIco.transform, 0, 0.5f, 44, 44, 26, 0);
            _stonesText = NewText("StonesText", stoneChip.transform, "0", 28, Accent, TextAlignmentOptions.Left, FontStyles.Bold);
            Anchor((RectTransform)_stonesText.transform, 0, 0.5f, 120, 54, 90, 0);
        }

        void BuildLoadoutPanel(RectTransform root)
        {
            RectTransform panel = NewRect("LoadoutPanel", root);
            Image bg = NewImage("PanelBg", panel, Panel);
            Stretch((RectTransform)bg.transform, 0, 0, 0, 0);
            Image edge = NewImage("PanelEdge", panel, new Color(0.94f, 0.76f, 0.31f, 0.28f));
            RectTransform et = (RectTransform)edge.transform;
            et.anchorMin = new Vector2(0, 1); et.anchorMax = new Vector2(1, 1);
            et.pivot = new Vector2(0.5f, 1); et.sizeDelta = new Vector2(0, 3);
            et.anchoredPosition = Vector2.zero;

            _prevHeroButton = NewButton("PrevHero", panel, PanelSoft, () => CycleHero(-1));
            Anchor((RectTransform)_prevHeroButton.transform, 0, 1, 64, 64, 46, -34);
            NewText("PrevLabel", _prevHeroButton.transform, "<", 38, Ink, TextAlignmentOptions.Center, FontStyles.Bold)
                .rectTransform.StretchFill();

            _nextHeroButton = NewButton("NextHero", panel, PanelSoft, () => CycleHero(1));
            Anchor((RectTransform)_nextHeroButton.transform, 1, 1, 64, 64, -46, -34);
            NewText("NextLabel", _nextHeroButton.transform, ">", 38, Ink, TextAlignmentOptions.Center, FontStyles.Bold)
                .rectTransform.StretchFill();

            _heroNameText = NewText("HeroName", panel, "-", 34, Ink, TextAlignmentOptions.Center, FontStyles.Bold);
            Anchor((RectTransform)_heroNameText.transform, 0.5f, 1, 400, 54, 0, -36);
            _powerText = NewText("HeroPower", panel, "PWR 0", 26, Gold, TextAlignmentOptions.Center, FontStyles.Bold);
            Anchor((RectTransform)_powerText.transform, 0.5f, 1, 400, 42, 0, -78);

            _portraitImage = NewImage("Portrait", panel, new Color(0.08f, 0.10f, 0.18f, 1f));
            Anchor((RectTransform)_portraitImage.transform, 0.5f, 1, 290, 290, 0, -250);
            _portraitImage.preserveAspect = true;
            Image portraitBar = NewImage("PortraitBar", panel, new Color(0.94f, 0.76f, 0.31f, 0.5f));
            Anchor((RectTransform)portraitBar.transform, 0.5f, 1, 298, 4, 0, -397);

            // 6 slots flanking the portrait: 3 left, 3 right.
            float sx = 235, topY = -130, step = SlotCellSize + 14;
            EquipmentSlot[] order =
            {
                EquipmentSlot.Weapon, EquipmentSlot.Helmet, EquipmentSlot.Armor,
                EquipmentSlot.Accessory, EquipmentSlot.Boots, EquipmentSlot.Relic,
            };
            for (int i = 0; i < 6; i++)
            {
                float x = i < 3 ? -sx : sx;
                float y = topY - (i % 3) * step;
                EquipmentSlot slotEnum = order[i];

                Image frame = NewImage("Slot_" + slotEnum, panel, new Color(0.14f, 0.17f, 0.28f, 1f));
                RectTransform fr = (RectTransform)frame.transform;
                fr.anchorMin = fr.anchorMax = new Vector2(0.5f, 1);
                fr.pivot = new Vector2(0.5f, 1);
                fr.sizeDelta = new Vector2(SlotCellSize, SlotCellSize);
                fr.anchoredPosition = new Vector2(x, y);
                frame.raycastTarget = true;

                Button btn = frame.gameObject.AddComponent<Button>();
                btn.targetGraphic = frame;
                EquipmentSlot captured = slotEnum;
                btn.onClick.AddListener(() => OnSlotTapped(captured));

                Image icon = NewImage("Icon", frame.transform, Color.white);
                Stretch((RectTransform)icon.transform, 8, 8, 8, 8);
                icon.preserveAspect = true;
                icon.enabled = false;

                TextMeshProUGUI lvl = NewText("Lvl", frame.transform, "", 24, Ink,
                    TextAlignmentOptions.BottomRight, FontStyles.Bold);
                Stretch((RectTransform)lvl.transform, 0, 0, 8, 4);

                TextMeshProUGUI slotLabel = NewText("SlotLabel", frame.transform, SlotNames[(int)slotEnum],
                    20, Muted, TextAlignmentOptions.Center);
                RectTransform sl = (RectTransform)slotLabel.transform;
                sl.anchorMin = new Vector2(0, 0); sl.anchorMax = new Vector2(1, 0);
                sl.pivot = new Vector2(0.5f, 1);
                sl.sizeDelta = new Vector2(0, 26);
                sl.anchoredPosition = new Vector2(0, -2);

                _slotViews[slotEnum] = new SlotView { Icon = icon, Frame = frame, Level = lvl };
            }
        }

        void BuildSetsPanel(RectTransform root)
        {
            RectTransform panel = NewRect("SetsPanel", root);
            Image bg = NewImage("PanelBg", panel, Panel);
            Stretch((RectTransform)bg.transform, 0, 0, 0, 0);

            TextMeshProUGUI title = NewText("SetsTitle", panel, "SET BONUSES", 26, Gold,
                TextAlignmentOptions.Left, FontStyles.Bold);
            Anchor((RectTransform)title.transform, 0, 1, 320, 40, 184, -26);
            title.characterSpacing = 8;

            _setsContent = NewRect("SetsContent", panel);
            var layout = _setsContent.gameObject.AddComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(24, 24, 62, 12);
            layout.spacing = 4;
            layout.childForceExpandWidth = true;
            layout.childForceExpandHeight = false;
            layout.childControlWidth = true;
            layout.childControlHeight = true;
            var fitter = _setsContent.gameObject.AddComponent<ContentSizeFitter>();
            fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            Stretch(_setsContent, 0, 0, 0, 0);
        }

        void BuildGridPanel(RectTransform root)
        {
            RectTransform panel = NewRect("GridPanel", root);
            Image bg = NewImage("PanelBg", panel, Panel);
            Stretch((RectTransform)bg.transform, 0, 0, 0, 0);

            TextMeshProUGUI title = NewText("GridTitle", panel, "INVENTORY", 26, Gold,
                TextAlignmentOptions.Left, FontStyles.Bold);
            Anchor((RectTransform)title.transform, 0, 1, 320, 40, 184, -24);
            title.characterSpacing = 8;

            string[] chipNames = { "All", "Weapon", "Helmet", "Armor", "Boots", "Accessory", "Relic" };
            float chipW = 126, gap = 8, x = 20;
            for (int i = 0; i < chipNames.Length; i++)
            {
                int captured = i - 1;
                Button chip = NewButton("Chip_" + chipNames[i], panel, PanelSoft,
                    () => { _filter = captured < 0 ? (EquipmentSlot?)null : (EquipmentSlot)captured; RebuildGrid(); });
                RectTransform cr = (RectTransform)chip.transform;
                cr.anchorMin = cr.anchorMax = new Vector2(0, 1);
                cr.pivot = new Vector2(0, 1);
                cr.sizeDelta = new Vector2(chipW, 50);
                cr.anchoredPosition = new Vector2(x, -60);
                x += chipW + gap;
                TextMeshProUGUI label = NewText("Label", chip.transform, chipNames[i], 22, Muted, TextAlignmentOptions.Center);
                label.rectTransform.StretchFill();
                _chipLabels.Add(label);
            }

            RectTransform scrollGo = NewRect("Scroll", panel);
            Stretch(scrollGo, 10, 124, 10, 10);
            _gridScroll = scrollGo.gameObject.AddComponent<ScrollRect>();
            Image scrollBg = NewImage("ScrollBg", scrollGo, new Color(0, 0, 0, 0.18f));
            Stretch((RectTransform)scrollBg.transform, 0, 0, 0, 0);
            scrollBg.raycastTarget = true;
            var mask = scrollGo.gameObject.AddComponent<Mask>();
            mask.showMaskGraphic = true;
            _gridScroll.viewport = scrollGo;

            _gridContent = NewRect("Content", scrollGo);
            _gridContent.anchorMin = new Vector2(0, 1);
            _gridContent.anchorMax = new Vector2(1, 1);
            _gridContent.pivot = new Vector2(0.5f, 1);
            var grid = _gridContent.gameObject.AddComponent<GridLayoutGroup>();
            grid.cellSize = new Vector2(CellSize, CellSize);
            grid.spacing = new Vector2(CellSpacing, CellSpacing);
            grid.padding = new RectOffset(14, 14, 14, 14);
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = 4;
            grid.childAlignment = TextAnchor.UpperCenter;
            var fitter = _gridContent.gameObject.AddComponent<ContentSizeFitter>();
            fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            _gridScroll.content = _gridContent;
            _gridScroll.horizontal = false;
            _gridScroll.movementType = ScrollRect.MovementType.Elastic;
            _gridScroll.scrollSensitivity = 30;

            _gridEmptyText = NewText("GridEmpty", scrollGo,
                _inventory.Count == 0 && !_filter.HasValue
                    ? "No equipment data available.\nEquipment is not persisted yet."
                    : "No equipment in this filter.",
                30, Muted, TextAlignmentOptions.Center);
            Stretch((RectTransform)_gridEmptyText.transform, 0, 0, 0, 0);
            _gridEmptyText.gameObject.SetActive(false);
        }

        void BuildDetailPanel(RectTransform root)
        {
            RectTransform panel = NewRect("DetailPanel", root);
            Image bg = NewImage("PanelBg", panel, Panel);
            Stretch((RectTransform)bg.transform, 0, 0, 0, 0);
            Image edge = NewImage("PanelEdge", panel, new Color(0.45f, 0.72f, 1f, 0.30f));
            RectTransform et = (RectTransform)edge.transform;
            et.anchorMin = new Vector2(0, 1); et.anchorMax = new Vector2(1, 1);
            et.pivot = new Vector2(0.5f, 1); et.sizeDelta = new Vector2(0, 3);
            et.anchoredPosition = Vector2.zero;

            _detailFrame = NewImage("IconFrame", panel, PanelSoft);
            RectTransform df = (RectTransform)_detailFrame.transform;
            df.anchorMin = df.anchorMax = new Vector2(0, 1);
            df.pivot = new Vector2(0, 1);
            df.sizeDelta = new Vector2(148, 148);
            df.anchoredPosition = new Vector2(24, -24);

            _detailIcon = NewImage("Icon", _detailFrame.transform, Color.white);
            Stretch((RectTransform)_detailIcon.transform, 10, 10, 10, 10);
            _detailIcon.preserveAspect = true;

            _detailName = NewText("Name", panel, "Select an item", 32, Ink, TextAlignmentOptions.Left, FontStyles.Bold);
            Anchor((RectTransform)_detailName.transform, 0, 1, 560, 44, 200, -34);
            _detailMeta = NewText("Meta", panel, "", 24, Muted, TextAlignmentOptions.Left);
            Anchor((RectTransform)_detailMeta.transform, 0, 1, 560, 36, 200, -76);
            _detailSet = NewText("Set", panel, "", 24, Accent, TextAlignmentOptions.Left);
            Anchor((RectTransform)_detailSet.transform, 0, 1, 560, 36, 200, -112);

            _detailStats = NewText("Stats", panel, "", 26, Ink, TextAlignmentOptions.TopLeft);
            RectTransform st = (RectTransform)_detailStats.transform;
            st.anchorMin = new Vector2(0, 1); st.anchorMax = new Vector2(1, 1);
            st.pivot = new Vector2(0.5f, 1);
            st.sizeDelta = new Vector2(-48, 132);
            st.anchoredPosition = new Vector2(0, -252);

            _detailStatus = NewText("Status", panel, "", 24, Bad, TextAlignmentOptions.Left);
            Anchor((RectTransform)_detailStatus.transform, 0, 1, 700, 36, 374, -330);

            float btnH = 80, btnW = 210, gap = 16, startX = 24, btnY = 404;
            _equipButton = NewButton("EquipBtn", panel, new Color(0.20f, 0.45f, 0.30f, 1f), OnEquipPressed);
            Anchor((RectTransform)_equipButton.transform, 0, 1, btnW, btnH, startX + btnW / 2, -btnY);
            _equipLabel = NewText("L", _equipButton.transform, "EQUIP", 26, Ink, TextAlignmentOptions.Center, FontStyles.Bold);
            _equipLabel.rectTransform.StretchFill();

            _unequipButton = NewButton("UnequipBtn", panel, new Color(0.32f, 0.26f, 0.40f, 1f), OnUnequipPressed);
            Anchor((RectTransform)_unequipButton.transform, 0, 1, btnW, btnH, startX + btnW + gap + btnW / 2, -btnY);
            NewText("L", _unequipButton.transform, "REMOVE", 26, Ink, TextAlignmentOptions.Center, FontStyles.Bold)
                .rectTransform.StretchFill();

            _enhanceButton = NewButton("EnhanceBtn", panel, new Color(0.55f, 0.40f, 0.14f, 1f), OnEnhancePressed);
            Anchor((RectTransform)_enhanceButton.transform, 0, 1, btnW + 80, btnH, startX + 2 * (btnW + gap) + (btnW + 80) / 2, -btnY);
            _enhanceLabel = NewText("L", _enhanceButton.transform, "ENHANCE", 25, Ink, TextAlignmentOptions.Center, FontStyles.Bold);
            _enhanceLabel.rectTransform.StretchFill();

            _lockButton = NewButton("LockBtn", panel, PanelSoft, OnLockPressed);
            Anchor((RectTransform)_lockButton.transform, 1, 1, 80, btnH, -64, -btnY);
            _lockLabel = NewText("L", _lockButton.transform, "L", 30, Ink, TextAlignmentOptions.Center, FontStyles.Bold);
            _lockLabel.rectTransform.StretchFill();
        }

        void BuildToast(RectTransform root)
        {
            Image bg = NewImage("ToastBg", root, new Color(0.05f, 0.06f, 0.12f, 0.92f));
            _toastRoot = (RectTransform)bg.transform;
            RectTransform br = _toastRoot;
            br.anchorMin = br.anchorMax = new Vector2(0.5f, 0);
            br.pivot = new Vector2(0.5f, 0);
            br.sizeDelta = new Vector2(900, 88);
            br.anchoredPosition = new Vector2(0, 46);
            bg.gameObject.SetActive(false);

            _toastText = NewText("Toast", bg.transform, "", 28, Ink, TextAlignmentOptions.Center, FontStyles.Bold);
            _toastText.rectTransform.StretchFill();
        }

        /// <summary>
        /// Portrait-first stacking: header on top, loadout left, detail right,
        /// a set-bonus strip, then the scrollable inventory grid.
        /// </summary>
        void LayoutForPortrait(RectTransform root)
        {
            RectTransform loadout = (RectTransform)root.Find("LoadoutPanel");
            RectTransform sets = (RectTransform)root.Find("SetsPanel");
            RectTransform grid = (RectTransform)root.Find("GridPanel");
            RectTransform detail = (RectTransform)root.Find("DetailPanel");

            loadout.anchorMin = new Vector2(0, 0.55f);
            loadout.anchorMax = new Vector2(0.47f, 1);
            loadout.offsetMin = new Vector2(14, 178);
            loadout.offsetMax = new Vector2(-8, -8);

            detail.anchorMin = new Vector2(0.47f, 0.55f);
            detail.anchorMax = new Vector2(1, 1);
            detail.offsetMin = new Vector2(8, 178);
            detail.offsetMax = new Vector2(-14, -8);

            sets.anchorMin = new Vector2(0, 0.42f);
            sets.anchorMax = new Vector2(1, 0.55f);
            sets.offsetMin = new Vector2(14, 0);
            sets.offsetMax = new Vector2(-14, 0);

            grid.anchorMin = new Vector2(0, 0);
            grid.anchorMax = new Vector2(1, 0.42f);
            grid.offsetMin = new Vector2(14, 14);
            grid.offsetMax = new Vector2(-14, -8);
        }

        // ------------------------------------------------------------------
        // Refresh — everything re-reads domain state, never cached results.
        // ------------------------------------------------------------------
        void RefreshAll()
        {
            RefreshHeader();
            RefreshLoadout();
            RefreshSets();
            RebuildGrid();
            RefreshDetail();
        }

        void RefreshHeader()
        {
            // The wallet chip shows authoritative progression gold. Equipment
            // gold/stones are a separate domain wallet that cannot be backed by
            // any persisted state yet, so they stay at their zero defaults.
            long goldDisplay = 0;
            try
            {
                var state = AwakenedRealm.Persistence.ProgressionSave.LoadState();
                if (state != null && state.Gold > 0)
                    goldDisplay = state.Gold;
            }
            catch (Exception) { }
            _goldText.text = goldDisplay.ToString("N0");
            _stonesText.text = _inventory.Wallet.EnhancementStones.ToString("N0");
            bool canCycle = _heroes.Count > 1 && !_busy;
            if (_prevHeroButton != null) _prevHeroButton.interactable = canCycle;
            if (_nextHeroButton != null) _nextHeroButton.interactable = canCycle;
            if (_heroes.Count == 0)
            {
                _heroNameText.text = "No owned heroes";
                _powerText.text = "Progression data unavailable";
                _portraitImage.sprite = null;
                _portraitImage.color = new Color(0.08f, 0.10f, 0.18f, 1f);
                return;
            }
            HeroRef hero = _heroes[Mathf.Clamp(_heroIndex, 0, _heroes.Count - 1)];
            _heroNameText.text = hero.Name;
            _powerText.text = "PWR " + Mathf.RoundToInt(
                EquipmentPower.LoadoutPower(hero.Id, _loadouts, _inventory, _catalog)).ToString("N0");
            _portraitImage.sprite = hero.Portrait;
            _portraitImage.color = hero.Portrait != null ? Color.white : new Color(0.08f, 0.10f, 0.18f, 1f);
        }

        void RefreshLoadout()
        {
            string heroId = CurrentHeroId;
            for (int i = 0; i < 6; i++)
            {
                EquipmentSlot slot = (EquipmentSlot)i;
                SlotView view = _slotViews[slot];
                string instId = _loadouts.GetEquipped(heroId, slot);
                EquipmentInstance inst = instId != null ? _inventory.Find(instId) : null;
                EquipmentDefinition def = inst != null ? _catalog.Find(inst.DefinitionId) : null;

                view.Icon.sprite = def != null ? ArtFor(def) : null;
                view.Icon.enabled = def != null;
                view.Frame.color = def != null
                    ? Color.Lerp(RarityColors[(int)def.Rarity], new Color(0.14f, 0.17f, 0.28f, 1f), 0.55f)
                    : new Color(0.14f, 0.17f, 0.28f, 1f);
                view.Level.text = inst != null && inst.EnhancementLevel > 0
                    ? "+" + inst.EnhancementLevel : string.Empty;
            }
        }

        void RefreshSets()
        {
            for (int i = _setsContent.childCount - 1; i >= 0; i--)
                Destroy(_setsContent.GetChild(i).gameObject);

            string heroId = CurrentHeroId;
            var counts = new Dictionary<string, int>(StringComparer.Ordinal);
            List<string> equipped = _loadouts.EquippedInstances(heroId);
            for (int i = 0; i < equipped.Count; i++)
            {
                EquipmentInstance inst = _inventory.Find(equipped[i]);
                EquipmentDefinition def = inst != null ? _catalog.Find(inst.DefinitionId) : null;
                if (def == null || string.IsNullOrEmpty(def.SetId))
                    continue;
                int c; counts.TryGetValue(def.SetId, out c); counts[def.SetId] = c + 1;
            }

            if (counts.Count == 0)
            {
                TextMeshProUGUI empty = NewText("Empty", _setsContent,
                    heroId == null
                        ? "No hero progression available."
                        : "No set pieces equipped on this hero.",
                    24, Muted, TextAlignmentOptions.Left);
                empty.gameObject.AddComponent<LayoutElement>().preferredHeight = 40;
                return;
            }

            var setIds = new List<string>(counts.Keys);
            setIds.Sort(StringComparer.Ordinal);
            List<StatModifier> active = EquipmentSetBonuses.AggregateActiveModifiers(
                heroId, _loadouts, _inventory, _catalog);

            for (int i = 0; i < setIds.Count; i++)
            {
                string setId = setIds[i];
                EquipmentSetBonuses.SetBonusDefinition def = EquipmentSetBonuses.Find(setId);
                int pieces = counts[setId];
                bool two = pieces >= EquipmentSetBonuses.TwoPieceThreshold;
                bool four = pieces >= EquipmentSetBonuses.FourPieceThreshold;

                var sb = new StringBuilder();
                sb.Append(PrettifySetId(setId)).Append("  ").Append(pieces).Append("/4");
                if (def != null)
                {
                    sb.Append("   2pc ");
                    sb.Append(two ? ModsInline(def.TwoPiece) : "inactive");
                    sb.Append("   4pc ");
                    sb.Append(four ? ModsInline(def.FourPiece) : "inactive");
                }

                TextMeshProUGUI row = NewText("Set_" + setId, _setsContent, sb.ToString(),
                    23, (two || four) ? Ink : Muted, TextAlignmentOptions.Left);
                row.gameObject.AddComponent<LayoutElement>().preferredHeight = 44;
            }

            if (active.Count > 0)
            {
                var flats = new Dictionary<EquipmentStatType, float>();
                var pcts = new Dictionary<EquipmentStatType, float>();
                for (int i = 0; i < active.Count; i++)
                {
                    float v; flats.TryGetValue(active[i].Stat, out v); flats[active[i].Stat] = v + active[i].Flat;
                    float p; pcts.TryGetValue(active[i].Stat, out p); pcts[active[i].Stat] = p + active[i].Percent;
                }
                var sb = new StringBuilder("Active: ");
                bool first = true;
                foreach (var kv in flats)
                {
                    if (!first) sb.Append(", ");
                    float p = pcts[kv.Key];
                    sb.Append(StatLabel(kv.Key)).Append(" +");
                    bool wrote = false;
                    if (kv.Value != 0f) { sb.Append(FormatNumber(kv.Value)); wrote = true; }
                    if (p != 0f) sb.Append(wrote ? " / +" : string.Empty).Append((p * 100f).ToString("0.#")).Append('%');
                    first = false;
                }
                TextMeshProUGUI row = NewText("SetActive", _setsContent, sb.ToString(),
                    23, Good, TextAlignmentOptions.Left);
                row.gameObject.AddComponent<LayoutElement>().preferredHeight = 40;
            }
        }

        void RebuildGrid()
        {
            for (int i = _gridContent.childCount - 1; i >= 0; i--)
                Destroy(_gridContent.GetChild(i).gameObject);

            var items = new List<EquipmentInstance>();
            for (int i = 0; i < _inventory.Items.Count; i++)
            {
                EquipmentInstance inst = _inventory.Items[i];
                if (inst == null) continue;
                EquipmentDefinition def = _catalog.Find(inst.DefinitionId);
                if (def == null) continue;
                if (_filter.HasValue && def.Slot != _filter.Value) continue;
                items.Add(inst);
            }

            items.Sort((a, b) =>
            {
                EquipmentDefinition da = _catalog.Find(a.DefinitionId);
                EquipmentDefinition db = _catalog.Find(b.DefinitionId);
                int r = db.Rarity.CompareTo(da.Rarity);
                if (r != 0) return r;
                return string.CompareOrdinal(da.DisplayName, db.DisplayName);
            });

            if (items.Count == 0)
            {
                _gridEmptyText.text = _inventory.Count == 0
                    ? "No equipment data available.\nEquipment is not persisted yet."
                    : "No equipment in this filter.";
            }
            _gridEmptyText.gameObject.SetActive(items.Count == 0);

            for (int i = 0; i < items.Count; i++)
            {
                EquipmentInstance inst = items[i];
                EquipmentDefinition def = _catalog.Find(inst.DefinitionId);
                Image cell = NewImage("Cell", _gridContent, new Color(0.12f, 0.14f, 0.23f, 1f));
                cell.raycastTarget = true;

                Sprite frameSprite = _rarityFrames != null && (int)def.Rarity < _rarityFrames.Length
                    ? _rarityFrames[(int)def.Rarity] : null;
                Image frame = NewImage("Frame", cell.transform,
                    frameSprite != null ? Color.white
                        : new Color(RarityColors[(int)def.Rarity].r, RarityColors[(int)def.Rarity].g,
                            RarityColors[(int)def.Rarity].b, 0.30f),
                    frameSprite);
                Stretch((RectTransform)frame.transform, 0, 0, 0, 0);
                frame.preserveAspect = true;

                Image icon = NewImage("Icon", cell.transform, Color.white, ArtFor(def));
                Stretch((RectTransform)icon.transform, 16, 16, 16, 16);
                icon.preserveAspect = true;

                TextMeshProUGUI lvl = NewText("Lvl", cell.transform,
                    inst.EnhancementLevel > 0 ? "+" + inst.EnhancementLevel : "Lv" + def.LevelRequirement,
                    20, inst.EnhancementLevel > 0 ? Gold : Muted, TextAlignmentOptions.BottomRight, FontStyles.Bold);
                Stretch((RectTransform)lvl.transform, 0, 0, 6, 4);

                if (_loadouts.IsEquipped(inst.InstanceId))
                {
                    TextMeshProUGUI eq = NewText("Eq", cell.transform, "E",
                        24, Good, TextAlignmentOptions.TopLeft, FontStyles.Bold);
                    Stretch((RectTransform)eq.transform, 8, 6, 0, 0);
                }
                if (inst.Locked)
                {
                    TextMeshProUGUI lk = NewText("Lock", cell.transform, "L",
                        24, Bad, TextAlignmentOptions.TopRight, FontStyles.Bold);
                    Stretch((RectTransform)lk.transform, 0, 6, 8, 0);
                }

                Button btn = cell.gameObject.AddComponent<Button>();
                btn.targetGraphic = cell;
                string id = inst.InstanceId;
                btn.onClick.AddListener(() => SelectItem(id));

                if (inst.InstanceId == _selectedInstanceId)
                    cell.color = new Color(0.24f, 0.30f, 0.45f, 1f);
            }

            for (int i = 0; i < _chipLabels.Count; i++)
                _chipLabels[i].color = (i == 0 && !_filter.HasValue) ||
                    (_filter.HasValue && i == (int)_filter.Value + 1) ? Gold : Muted;

            _gridScroll.verticalNormalizedPosition = 1f;
        }

        void RefreshDetail()
        {
            string heroId = CurrentHeroId;
            EquipmentInstance inst = _selectedInstanceId != null ? _inventory.Find(_selectedInstanceId) : null;
            EquipmentDefinition def = inst != null ? _catalog.Find(inst.DefinitionId) : null;
            bool has = def != null;

            _detailIcon.enabled = has;
            _detailIcon.sprite = has ? ArtFor(def) : null;
            _detailFrame.color = has
                ? Color.Lerp(RarityColors[(int)def.Rarity], PanelSoft, 0.45f) : PanelSoft;
            _detailName.text = has ? def.DisplayName : "Select an item";
            _detailMeta.text = has
                ? RarityNames[(int)def.Rarity] + "  |  " + SlotNames[(int)def.Slot] +
                  "  |  Req Lv " + def.LevelRequirement +
                  "  |  +" + inst.EnhancementLevel + "/" + EnhancementRules.MaxEnhancement(def.Rarity)
                : string.Empty;
            _detailSet.text = has && !string.IsNullOrEmpty(def.SetId)
                ? "Set: " + PrettifySetId(def.SetId) : string.Empty;

            if (has)
            {
                var sb = new StringBuilder();
                float mult = EnhancementRules.EnhancementMultiplier(inst.EnhancementLevel);
                for (int i = 0; i < def.BaseStats.Count; i++)
                {
                    StatModifier m = def.BaseStats[i];
                    sb.Append(StatLabel(m.Stat)).Append(' ');
                    if (m.Flat != 0f)
                        sb.Append('+').Append(FormatNumber(m.Flat * mult));
                    if (m.Percent != 0f)
                    {
                        if (m.Flat != 0f) sb.Append("  ");
                        sb.Append('+').Append((m.Percent * mult * 100f).ToString("0.#")).Append('%');
                    }
                    sb.Append('\n');
                }
                sb.Append("Power ").Append(Mathf.RoundToInt(EquipmentPower.InstancePower(inst, def)).ToString("N0"));
                _detailStats.text = sb.ToString();
            }
            else
            {
                _detailStats.text = heroId == null && _inventory.Count == 0
                    ? "No equipment or hero data is available yet.\nProgress through the campaign to unlock heroes."
                    : "Tap an inventory cell or an equipment slot.";
            }

            bool equippedByThis = has && heroId == _loadouts.EquippedHeroId(inst.InstanceId);
            bool equippedByOther = has && _loadouts.IsEquipped(inst.InstanceId) && !equippedByThis;
            bool atCap = has && inst.EnhancementLevel >= EnhancementRules.MaxEnhancement(def.Rarity);

            _equipButton.interactable = has && !equippedByThis && !equippedByOther && !_busy;
            _equipLabel.text = equippedByOther ? "ON OTHER" : (equippedByThis ? "EQUIPPED" : "EQUIP");
            _unequipButton.interactable = equippedByThis && !_busy;
            _lockButton.interactable = has && !_busy;
            _lockLabel.text = has && inst.Locked ? "U" : "L";
            _lockLabel.color = has && inst.Locked ? Bad : Muted;

            // Mutations require an authoritative instance selection; without a
            // persisted inventory nothing may be equipped, removed, or locked.
            if (!has)
            {
                _equipButton.interactable = false;
                _unequipButton.interactable = false;
                _lockButton.interactable = false;
            }

            if (!has)
            {
                _detailStatus.text = string.Empty;
                _enhanceButton.interactable = false;
                _enhanceLabel.text = "ENHANCE";
            }
            else if (atCap)
            {
                _detailStatus.text = "Max enhancement reached.";
                _detailStatus.color = Gold;
                _enhanceButton.interactable = false;
                _enhanceLabel.text = "MAXED";
            }
            else
            {
                long gold; int stones;
                EnhancementRules.CostForLevel(def.Rarity, inst.EnhancementLevel + 1, out gold, out stones);
                bool afford = _inventory.Wallet.CanAfford(gold, stones);
                _enhanceButton.interactable = afford && !_busy;
                _enhanceLabel.text = "+" + (inst.EnhancementLevel + 1) + "  " +
                    gold.ToString("N0") + "g " + stones + "st";
                if (!afford)
                {
                    _detailStatus.text = "Insufficient gold or enhancement stones.";
                    _detailStatus.color = Bad;
                }
                else if (equippedByOther)
                {
                    _detailStatus.text = "Equipped on another hero.";
                    _detailStatus.color = Muted;
                }
                else
                {
                    _detailStatus.text = string.Empty;
                }
            }
        }

        // ------------------------------------------------------------------
        // Actions — exactly one domain call each, then a full refresh.
        // ------------------------------------------------------------------
        void SelectItem(string instanceId)
        {
            _selectedInstanceId = instanceId;
            if (_gridContent != null)
                RebuildGrid();
            if (_detailName != null)
                RefreshDetail();
        }

        void OnSlotTapped(EquipmentSlot slot)
        {
            if (_busy) return;
            string instId = _loadouts.GetEquipped(CurrentHeroId, slot);
            if (instId != null)
            {
                SelectItem(instId);
            }
            else
            {
                _filter = slot;
                SelectItem(null);
                Toast(SlotNames[(int)slot] + " slot is empty — pick an item below.");
            }
        }

        void OnEquipPressed()
        {
            if (_busy || CurrentHeroId == null) return;
            if (_selectedInstanceId == null || !_inventory.Contains(_selectedInstanceId))
            {
                Toast("No equipment is available to equip.");
                return;
            }
            _busy = true;
            _equipButton.interactable = false;

            bool ok = _loadouts.TryEquip(CurrentHeroId, _selectedInstanceId, _inventory, _catalog);
            Toast(ok ? "Equipped." : "Cannot equip that item.");

            _busy = false;
            RefreshAll();
        }

        void OnUnequipPressed()
        {
            if (_busy || CurrentHeroId == null) return;
            EquipmentInstance inst = _selectedInstanceId != null ? _inventory.Find(_selectedInstanceId) : null;
            EquipmentDefinition def = inst != null ? _catalog.Find(inst.DefinitionId) : null;
            if (def == null)
            {
                Toast("No equipment is available to remove.");
                return;
            }
            _busy = true;
            _unequipButton.interactable = false;

            string removed = _loadouts.Unequip(CurrentHeroId, def.Slot);
            Toast(removed != null ? "Unequipped." : "Nothing to remove.");

            _busy = false;
            RefreshAll();
        }

        void OnEnhancePressed()
        {
            if (_busy) return;
            EquipmentInstance inst = _selectedInstanceId != null ? _inventory.Find(_selectedInstanceId) : null;
            EquipmentDefinition def = inst != null ? _catalog.Find(inst.DefinitionId) : null;
            if (def == null)
            {
                Toast("No equipment is available to enhance.");
                return;
            }
            _busy = true;
            _enhanceButton.interactable = false;

            bool ok = EnhancementRules.TryEnhance(inst, def, _inventory.Wallet);
            Toast(ok ? def.DisplayName + " enhanced to +" + inst.EnhancementLevel + "."
                     : "Enhancement failed — check cost and cap.");

            _busy = false;
            RefreshAll();
        }

        void OnLockPressed()
        {
            if (_busy) return;
            EquipmentInstance inst = _selectedInstanceId != null ? _inventory.Find(_selectedInstanceId) : null;
            if (inst == null)
            {
                Toast("No equipment is available to lock.");
                return;
            }
            _busy = true;
            _lockButton.interactable = false;

            bool ok = _inventory.SetLocked(inst.InstanceId, !inst.Locked);
            Toast(ok ? (inst.Locked ? "Item locked." : "Item unlocked.") : "Lock unchanged.");

            _busy = false;
            RefreshAll();
        }

        void CycleHero(int dir)
        {
            if (_busy || _heroes.Count == 0) return;
            _heroIndex = (_heroIndex + dir + _heroes.Count) % _heroes.Count;
            RefreshAll();
        }

        void OnBack()
        {
            // Blocked only while an atomic mutation is mid-flight or the scene
            // is already leaving; a second press must not double-load.
            if (_busy || _navigatingAway) return;
            _navigatingAway = true;
            _backButton.interactable = false;
            SceneManager.LoadScene(MainMenuSceneName);
        }

        void Toast(string message)
        {
            _toastText.text = message;
            _toastRoot.gameObject.SetActive(true);
            _toastUntil = Time.unscaledTime + 2.4f;
        }

        // ------------------------------------------------------------------
        // Formatting helpers
        // ------------------------------------------------------------------
        Sprite ArtFor(EquipmentDefinition def)
        {
            switch (def.Slot)
            {
                case EquipmentSlot.Weapon: return _artWeapon;
                case EquipmentSlot.Helmet: return _artHelmet;
                case EquipmentSlot.Armor: return _artArmor;
                case EquipmentSlot.Boots: return _artBoots;
                case EquipmentSlot.Accessory: return _artAccessory;
                case EquipmentSlot.Relic: return _artRelic;
                default: return null;
            }
        }

        static string PrettifySetId(string setId)
        {
            if (string.IsNullOrEmpty(setId)) return string.Empty;
            string s = setId.StartsWith("set_", StringComparison.Ordinal) ? setId.Substring(4) : setId;
            var sb = new StringBuilder();
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (c == '_') { sb.Append(' '); continue; }
                sb.Append(i == 0 || s[i - 1] == '_' ? char.ToUpperInvariant(c) : c);
            }
            return sb.ToString();
        }

        static string StatLabel(EquipmentStatType stat)
        {
            switch (stat)
            {
                case EquipmentStatType.HP: return "HP";
                case EquipmentStatType.ATK: return "ATK";
                case EquipmentStatType.DEF: return "DEF";
                case EquipmentStatType.MAG: return "MAG";
                case EquipmentStatType.SPD: return "SPD";
                case EquipmentStatType.CritRate: return "CRIT";
                case EquipmentStatType.Resistance: return "RES";
                default: return stat.ToString();
            }
        }

        static string FormatNumber(float v)
        {
            return Mathf.Approximately(v, Mathf.Round(v))
                ? Mathf.RoundToInt(v).ToString("N0")
                : v.ToString("0.##");
        }

        string ModsInline(StatModifier[] mods)
        {
            var sb = new StringBuilder();
            for (int i = 0; i < mods.Length; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append(StatLabel(mods[i].Stat)).Append(" +");
                if (mods[i].Flat != 0f) sb.Append(FormatNumber(mods[i].Flat));
                if (mods[i].Percent != 0f) sb.Append((mods[i].Percent * 100f).ToString("0.#")).Append('%');
            }
            return sb.ToString();
        }
    }

    internal static class EquipmentRectExtensions
    {
        public static void StretchFill(this RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
        }
    }
}
