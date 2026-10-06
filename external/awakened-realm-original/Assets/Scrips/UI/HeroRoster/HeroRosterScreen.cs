using System;
using System.Collections;
using System.Collections.Generic;
using AwakenedRealm.CombatV2;
using AwakenedRealm.Enums;
using AwakenedRealm.Keys;
using AwakenedRealm.Persistence;
using AwakenedRealm.Presentation;
using AwakenedRealm.Progression;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace AwakenedRealm.UI.HeroRoster
{
    /// <summary>
    /// Player-visible hero roster for the bounded HeroRoster scene. Reads the
    /// owned-hero progression state (ProgressionSave.LoadState) joined against
    /// HeroKitCatalog for display identity, drives a portrait-first roster grid,
    /// hero detail panel, and the star-up/evolution presentation.
    ///
    /// All star-up rules (requirements, caps, milestones) come from
    /// StarProgressionRules and each attempt goes through
    /// OwnedHeroProgression.TryStarUp exactly once; the UI never duplicates
    /// domain rules or invents currencies/copies.
    /// </summary>
    public sealed class HeroRosterScreen : MonoBehaviour
    {
        // Premium dark palette tuned to the generated roster art direction.
        static readonly Color PanelBg = new Color(0.10f, 0.09f, 0.18f, 0.93f);
        static readonly Color PanelBgLight = new Color(0.17f, 0.15f, 0.28f, 0.95f);
        static readonly Color BgTint = new Color(0.04f, 0.03f, 0.10f);
        static readonly Color Gold = new Color(0.96f, 0.78f, 0.38f);
        static readonly Color TextPrimary = new Color(0.96f, 0.94f, 0.99f);
        static readonly Color TextMuted = new Color(0.68f, 0.65f, 0.80f);
        static readonly Color AccentCyan = new Color(0.42f, 0.86f, 0.95f);
        static readonly Color DangerRed = new Color(0.94f, 0.40f, 0.40f);

        enum SortMode { Rarity, Stars, Level, Name }
        enum FilterMode { All, Rare, Epic, Legendary, Mythic }

        Canvas _canvas;
        RectTransform _root;
        GameProgressionState _state;
        SortMode _sort = SortMode.Rarity;
        FilterMode _filter = FilterMode.All;
        string _selectedHeroId;
        bool _navigatingAway;

        // Roster widgets
        RectTransform _gridContent;
        Text _headerStats;
        Text _emptyLabel;
        readonly List<HeroCardView> _cards = new List<HeroCardView>();
        readonly List<HeroCardView> _cardPool = new List<HeroCardView>();

        // Detail widgets
        GameObject _detailPanel;
        Image _detailPortrait;
        Image _detailFrame;
        Image _detailAura;
        Text _detailName;
        Text _detailMeta;
        RectTransform _detailStarsRow;
        Text _detailStats;
        RectTransform _abilityList;
        Text _reqCopies;
        Text _reqFodder;
        Text _starUpState;
        Button _starUpButton;
        Text _starUpLabel;

        // Ceremony overlay
        GameObject _ceremonyPanel;
        Image _ceremonyImage;
        Text _ceremonyText;
        Text _ceremonySubText;
        Coroutine _ceremonyRoutine;

        // Controls
        Text _sortLabel;
        Text _filterLabel;

        [Header("Typefaces")]
        [SerializeField] Font _bodyFont = null;
        [SerializeField] Font _displayFont = null;

        Font _font;

        void Awake()
        {
            _font = _bodyFont != null ? _bodyFont : LoadFont();
            _displayFont = _displayFont != null ? _displayFont : _font;
            BuildCanvas();
            LoadState();
            BuildStaticChrome();
            RebuildRoster();

            // Portrait-first: land on the first visible hero so the detail
            // panel reads populated immediately.
            List<OwnedHeroProgression> visible = VisibleHeroes();
            _selectedHeroId = visible.Count > 0 ? visible[0].HeroId : null;
            ShowDetail(SelectedHero);
            RefreshSelectionStates();
        }

        void OnDestroy()
        {
            HeroPortraitResolver.ClearCache();
        }

        void Update()
        {
            // Android system back (and editor Escape) routes through the same
            // guarded path as the on-screen Back button.
            if (Input.GetKeyDown(KeyCode.Escape))
                HandleSystemBack();
        }

        static Font LoadFont()
        {
            // Prefer the runtime built-in so the scene is self-contained.
            Font f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (f == null)
                f = Resources.GetBuiltinResource<Font>("Arial.ttf");
            return f;
        }

        // ------------------------------------------------------------------
        // State
        // ------------------------------------------------------------------

        void LoadState()
        {
            // Allow only ids authored in HeroKitCatalog; LoadState throws on
            // unknown/corrupt saves rather than presenting placeholder heroes.
            var allowed = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < HeroKitCatalog.All.Count; i++)
                allowed.Add(HeroKitCatalog.All[i].Id);

            try
            {
                _state = ProgressionSave.LoadState(allowed);
            }
            catch (Exception ex)
            {
                Debug.LogError("[HeroRoster] Failed to load progression state: " + ex.Message);
                _state = new GameProgressionState();
            }

            if (_state.Heroes == null)
                _state.Heroes = new List<OwnedHeroProgression>();
        }

        void SaveState()
        {
            try
            {
                ProgressionSave.SaveState(_state);
            }
            catch (Exception ex)
            {
                Debug.LogError("[HeroRoster] Failed to persist progression state: " + ex.Message);
            }
        }

        OwnedHeroProgression SelectedHero
        {
            get
            {
                if (string.IsNullOrEmpty(_selectedHeroId) || _state == null)
                    return null;
                return _state.FindHero(_selectedHeroId);
            }
        }

        // ------------------------------------------------------------------
        // Layout
        // ------------------------------------------------------------------

        void BuildCanvas()
        {
            var canvasGo = new GameObject(
                "HeroRosterCanvas",
                typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasGo.transform.SetParent(transform, false);
            _canvas = canvasGo.GetComponent<Canvas>();
            _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            _canvas.pixelPerfect = false;

            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1080f, 1920f);
            scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
            scaler.matchWidthOrHeight = 0.5f;

            var safeGo = new GameObject("SafeArea", typeof(RectTransform), typeof(UI_SafeArea));
            safeGo.transform.SetParent(canvasGo.transform, false);
            _root = (RectTransform)safeGo.transform;
            Stretch(_root);

            // Full-bleed generated roster backdrop when present; tint otherwise.
            var bg = CreateImage(_root, "Background", BgTint);
            Stretch(bg.rectTransform);
            Sprite rosterBg = PresentationVisuals.GetRoster();
            if (rosterBg != null)
            {
                bg.sprite = rosterBg;
                bg.color = Color.white;
                bg.preserveAspect = false;
            }

            // Soft dark vignette so text stays mobile-readable over the art.
            var vignette = CreateImage(_root, "Vignette", new Color(0.02f, 0.02f, 0.06f, 0.62f));
            Stretch(vignette.rectTransform);
            vignette.raycastTarget = false;
        }

        void BuildStaticChrome()
        {
            // ---- Header ----------------------------------------------------
            var header = CreateImage(_root, "Header", new Color(0.07f, 0.06f, 0.14f, 0.88f));
            Anchor(header.rectTransform, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(0f, -168f), Vector2.zero);

            var title = CreateText(header.rectTransform, "Title", "HERO ROSTER",
                54, FontStyle.Bold, TextAnchor.MiddleLeft, TextPrimary);
            title.font = _displayFont;
            Anchor(title.rectTransform, new Vector2(0f, 0.5f), new Vector2(1f, 0.5f),
                new Vector2(216f, -42f), new Vector2(-24f, 34f));

            _headerStats = CreateText(header.rectTransform, "Stats", "",
                30, FontStyle.Normal, TextAnchor.MiddleLeft, TextMuted);
            Anchor(_headerStats.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(216f, 8f), new Vector2(-24f, 60f));

            var back = CreateButton(header.rectTransform, "BackButton", "< BACK",
                30, OnBackPressed);
            Anchor(back.GetComponent<RectTransform>(), new Vector2(0f, 0f), new Vector2(0f, 1f),
                new Vector2(16f, 12f), new Vector2(200f, -12f));
            StyleButton(back, PanelBgLight, TextPrimary);
            back.gameObject.SetActive(CanGoBack());

            // ---- Filter / sort bar -----------------------------------------
            var bar = CreateImage(_root, "FilterBar", new Color(0.09f, 0.08f, 0.17f, 0.85f));
            Anchor(bar.rectTransform, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(0f, -264f), new Vector2(0f, -168f));

            var filterBtn = CreateButton(bar.rectTransform, "FilterButton", "",
                30, CycleFilter);
            Anchor(filterBtn.GetComponent<RectTransform>(), new Vector2(0f, 0f), new Vector2(0.5f, 1f),
                new Vector2(16f, 14f), new Vector2(-8f, -14f));
            StyleButton(filterBtn, PanelBgLight, Gold);
            _filterLabel = filterBtn.GetComponentInChildren<Text>();
            _filterLabel.fontStyle = FontStyle.Bold;

            var sortBtn = CreateButton(bar.rectTransform, "SortButton", "",
                30, CycleSort);
            Anchor(sortBtn.GetComponent<RectTransform>(), new Vector2(0.5f, 0f), new Vector2(1f, 1f),
                new Vector2(8f, 14f), new Vector2(-16f, -14f));
            StyleButton(sortBtn, PanelBgLight, AccentCyan);
            _sortLabel = sortBtn.GetComponentInChildren<Text>();
            _sortLabel.fontStyle = FontStyle.Bold;

            RefreshControlLabels();

            // ---- Scroll grid ------------------------------------------------
            var scrollGo = new GameObject("RosterScroll",
                typeof(RectTransform), typeof(ScrollRect), typeof(Image));
            scrollGo.transform.SetParent(_root, false);
            var scrollRect = (RectTransform)scrollGo.transform;
            // Leave the bottom 740 units clear so the detail panel does not
            // cover the last grid row; the panel slides up to meet the grid.
            Anchor(scrollRect, new Vector2(0f, 0f), new Vector2(1f, 1f),
                new Vector2(0f, 740f), new Vector2(0f, -264f));
            var scrollImg = scrollGo.GetComponent<Image>();
            scrollImg.color = new Color(0f, 0f, 0f, 0f);

            var viewportGo = new GameObject("Viewport",
                typeof(RectTransform), typeof(RectMask2D), typeof(Image));
            viewportGo.transform.SetParent(scrollGo.transform, false);
            var viewport = (RectTransform)viewportGo.transform;
            Stretch(viewport);
            viewportGo.GetComponent<Image>().color = new Color(0f, 0f, 0f, 0.01f);

            var contentGo = new GameObject("Content",
                typeof(RectTransform), typeof(GridLayoutGroup), typeof(ContentSizeFitter));
            contentGo.transform.SetParent(viewportGo.transform, false);
            _gridContent = (RectTransform)contentGo.transform;
            _gridContent.anchorMin = new Vector2(0f, 1f);
            _gridContent.anchorMax = new Vector2(1f, 1f);
            _gridContent.pivot = new Vector2(0.5f, 1f);
            _gridContent.offsetMin = new Vector2(20f, 0f);
            _gridContent.offsetMax = new Vector2(-20f, 0f);

            var grid = contentGo.GetComponent<GridLayoutGroup>();
            grid.cellSize = new Vector2(336f, 448f);
            grid.spacing = new Vector2(14f, 14f);
            grid.padding = new RectOffset(0, 0, 24, 24);
            grid.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            grid.constraintCount = 3;
            grid.childAlignment = TextAnchor.UpperCenter;

            var fitter = contentGo.GetComponent<ContentSizeFitter>();
            fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.content = _gridContent;
            scroll.viewport = viewport;
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.scrollSensitivity = 50f;
            scroll.movementType = ScrollRect.MovementType.Clamped;

            _emptyLabel = CreateText(_root, "EmptyLabel", "",
                38, FontStyle.Normal, TextAnchor.MiddleCenter, TextMuted);
            // Keep the empty-state copy inside the scroll region so it never
            // collides with the header or detail panel.
            Anchor(_emptyLabel.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 1f),
                new Vector2(60f, 740f), new Vector2(-60f, -320f));

            BuildDetailPanel();
            BuildCeremonyPanel();
        }

        void BuildDetailPanel()
        {
            _detailPanel = new GameObject("DetailPanel",
                typeof(RectTransform), typeof(Image));
            _detailPanel.transform.SetParent(_root, false);
            var panelRt = (RectTransform)_detailPanel.transform;
            Anchor(panelRt, new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(0f, 0f), new Vector2(0f, 740f));
            _detailPanel.GetComponent<Image>().color = PanelBg;

            // Portrait column
            var portraitBack = CreateImage(panelRt, "PortraitBack", PanelBgLight);
            Anchor(portraitBack.rectTransform, new Vector2(0f, 0f), new Vector2(0f, 1f),
                new Vector2(24f, 24f), new Vector2(364f, -24f));

            _detailAura = CreateImage(portraitBack.rectTransform, "Aura", new Color(1f, 1f, 1f, 0f));
            Stretch(_detailAura.rectTransform);
            _detailAura.preserveAspect = true;
            _detailAura.raycastTarget = false;

            _detailPortrait = CreateImage(portraitBack.rectTransform, "Portrait", new Color(1f, 1f, 1f, 0f));
            Stretch(_detailPortrait.rectTransform);
            _detailPortrait.preserveAspect = true;
            _detailPortrait.raycastTarget = false;

            _detailFrame = CreateImage(portraitBack.rectTransform, "Frame", new Color(1f, 1f, 1f, 0f));
            Stretch(_detailFrame.rectTransform);
            _detailFrame.preserveAspect = false;
            _detailFrame.raycastTarget = false;

            // Name / meta column
            _detailName = CreateText(panelRt, "Name", "",
                48, FontStyle.Bold, TextAnchor.MiddleLeft, TextPrimary);
            Anchor(_detailName.rectTransform, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(392f, -140f), new Vector2(-24f, -44f));

            _detailMeta = CreateText(panelRt, "Meta", "",
                30, FontStyle.Normal, TextAnchor.MiddleLeft, TextMuted);
            Anchor(_detailMeta.rectTransform, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(392f, -200f), new Vector2(-24f, -148f));

            _detailStarsRow = CreateRect(panelRt, "StarsRow");
            Anchor(_detailStarsRow, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(392f, -256f), new Vector2(-24f, -208f));

            _detailStats = CreateText(panelRt, "Stats", "",
                28, FontStyle.Normal, TextAnchor.MiddleLeft, TextPrimary);
            Anchor(_detailStats.rectTransform, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(392f, -330f), new Vector2(-24f, -264f));

            var abilitiesHeader = CreateText(panelRt, "AbilitiesHeader", "ABILITIES",
                24, FontStyle.Bold, TextAnchor.MiddleLeft, AccentCyan);
            Anchor(abilitiesHeader.rectTransform, new Vector2(0f, 1f), new Vector2(1f, 1f),
                new Vector2(392f, -384f), new Vector2(-24f, -338f));

            _abilityList = CreateRect(panelRt, "AbilityList");
            Anchor(_abilityList, new Vector2(0f, 0f), new Vector2(1f, 1f),
                new Vector2(392f, -560f), new Vector2(-24f, 190f));

            // Requirement rows
            var copiesCap = CreateText(panelRt, "ReqCopiesCap", "COPIES",
                22, FontStyle.Bold, TextAnchor.MiddleLeft, TextMuted);
            Anchor(copiesCap.rectTransform, new Vector2(0f, 0f), new Vector2(0.5f, 0f),
                new Vector2(392f, 156f), new Vector2(-8f, 182f));
            _reqCopies = CreateText(panelRt, "ReqCopies", "",
                34, FontStyle.Bold, TextAnchor.MiddleLeft, TextPrimary);
            Anchor(_reqCopies.rectTransform, new Vector2(0f, 0f), new Vector2(0.5f, 0f),
                new Vector2(392f, 118f), new Vector2(-8f, 158f));

            var fodderCap = CreateText(panelRt, "ReqFodderCap", "FODDER",
                22, FontStyle.Bold, TextAnchor.MiddleLeft, TextMuted);
            Anchor(fodderCap.rectTransform, new Vector2(0.5f, 0f), new Vector2(1f, 0f),
                new Vector2(8f, 156f), new Vector2(-24f, 182f));
            _reqFodder = CreateText(panelRt, "ReqFodder", "",
                34, FontStyle.Bold, TextAnchor.MiddleLeft, TextPrimary);
            Anchor(_reqFodder.rectTransform, new Vector2(0.5f, 0f), new Vector2(1f, 0f),
                new Vector2(8f, 118f), new Vector2(-24f, 158f));

            // Star-up button + hint line
            _starUpButton = CreateButton(panelRt, "StarUpButton", "",
                34, OnStarUpPressed);
            Anchor(_starUpButton.GetComponent<RectTransform>(), new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(392f, 40f), new Vector2(-24f, 110f));
            StyleButton(_starUpButton, new Color(0.30f, 0.24f, 0.10f), Gold);
            _starUpLabel = _starUpButton.GetComponentInChildren<Text>();
            _starUpLabel.fontStyle = FontStyle.Bold;

            _starUpState = CreateText(panelRt, "StarUpState", "",
                26, FontStyle.Normal, TextAnchor.MiddleCenter, TextMuted);
            Anchor(_starUpState.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(392f, 6f), new Vector2(-24f, 38f));
        }

        void BuildCeremonyPanel()
        {
            _ceremonyPanel = new GameObject("CeremonyPanel",
                typeof(RectTransform), typeof(Image), typeof(CanvasGroup));
            _ceremonyPanel.transform.SetParent(_root, false);
            var rt = (RectTransform)_ceremonyPanel.transform;
            Stretch(rt);
            var img = _ceremonyPanel.GetComponent<Image>();
            img.color = new Color(0f, 0f, 0f, 0.90f);

            _ceremonyImage = CreateImage(rt, "CeremonyArt", new Color(1f, 1f, 1f, 0f));
            Anchor(_ceremonyImage.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                new Vector2(-380f, -280f), new Vector2(380f, 380f));
            _ceremonyImage.preserveAspect = true;
            _ceremonyImage.raycastTarget = false;

            _ceremonyText = CreateText(rt, "CeremonyText", "",
                60, FontStyle.Bold, TextAnchor.MiddleCenter, Gold);
            Anchor(_ceremonyText.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(60f, 250f), new Vector2(-60f, 372f));

            _ceremonySubText = CreateText(rt, "CeremonySubText", "",
                32, FontStyle.Normal, TextAnchor.MiddleCenter, TextPrimary);
            Anchor(_ceremonySubText.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 0f),
                new Vector2(80f, 148f), new Vector2(-80f, 246f));

            var close = CreateButton(rt, "CeremonyClose", "CONTINUE",
                30, OnCeremonyClose);
            Anchor(close.GetComponent<RectTransform>(), new Vector2(0.5f, 0f), new Vector2(0.5f, 0f),
                new Vector2(-200f, 56f), new Vector2(200f, 132f));
            StyleButton(close, PanelBgLight, TextPrimary);

            _ceremonyPanel.SetActive(false);
        }

        // ------------------------------------------------------------------
        // Roster population
        // ------------------------------------------------------------------

        void RebuildRoster()
        {
            List<OwnedHeroProgression> heroes = VisibleHeroes();
            for (int i = 0; i < _cardPool.Count; i++)
                _cardPool[i].gameObject.SetActive(false);
            _cards.Clear();

            for (int i = 0; i < heroes.Count; i++)
            {
                HeroCardView card;
                if (i < _cardPool.Count)
                {
                    card = _cardPool[i];
                    card.gameObject.SetActive(true);
                }
                else
                {
                    card = HeroCardView.Create(_gridContent, _font, OnCardSelected);
                    _cardPool.Add(card);
                }

                OwnedHeroProgression owned = heroes[i];
                HeroKit kit;
                HeroKitCatalog.TryGet(owned.HeroId, out kit);
                card.Bind(owned, kit,
                    string.Equals(_selectedHeroId, owned.HeroId, StringComparison.Ordinal));
                _cards.Add(card);
            }

            _emptyLabel.text = heroes.Count == 0 ? EmptyMessage() : string.Empty;
            _headerStats.text = string.Format(
                "{0} heroes owned   ·   {1} shown",
                _state.Heroes.Count, heroes.Count);
        }

        string EmptyMessage()
        {
            if (_state.Heroes.Count == 0)
                return "No heroes owned yet.\nSummon heroes to build your roster.";
            return "No heroes match this filter.";
        }

        List<OwnedHeroProgression> VisibleHeroes()
        {
            var result = new List<OwnedHeroProgression>();
            for (int i = 0; i < _state.Heroes.Count; i++)
            {
                OwnedHeroProgression hero = _state.Heroes[i];
                if (hero == null || !HeroKitCatalog.Contains(hero.HeroId))
                    continue;
                if (_filter != FilterMode.All && hero.Rarity != ToRarity(_filter))
                    continue;
                result.Add(hero);
            }
            result.Sort(CompareHeroes);
            return result;
        }

        int CompareHeroes(OwnedHeroProgression a, OwnedHeroProgression b)
        {
            switch (_sort)
            {
                case SortMode.Stars:
                    int byStars = b.Stars.CompareTo(a.Stars);
                    return byStars != 0 ? byStars : CompareRarityThenName(a, b);
                case SortMode.Level:
                    int byLevel = b.Level.CompareTo(a.Level);
                    return byLevel != 0 ? byLevel : CompareRarityThenName(a, b);
                case SortMode.Name:
                    return string.CompareOrdinal(DisplayName(a), DisplayName(b));
                default:
                    return CompareRarityThenName(a, b);
            }
        }

        int CompareRarityThenName(OwnedHeroProgression a, OwnedHeroProgression b)
        {
            int byRarity = RarityRank(b.Rarity).CompareTo(RarityRank(a.Rarity));
            return byRarity != 0 ? byRarity : string.CompareOrdinal(DisplayName(a), DisplayName(b));
        }

        static int RarityRank(HeroRarity rarity)
        {
            switch (rarity)
            {
                case HeroRarity.mythic: return 4;
                case HeroRarity.legendary: return 3;
                case HeroRarity.epic: return 2;
                case HeroRarity.rare: return 1;
                default: return 0;
            }
        }

        static HeroRarity ToRarity(FilterMode filter)
        {
            switch (filter)
            {
                case FilterMode.Rare: return HeroRarity.rare;
                case FilterMode.Epic: return HeroRarity.epic;
                case FilterMode.Legendary: return HeroRarity.legendary;
                case FilterMode.Mythic: return HeroRarity.mythic;
                default: return HeroRarity.common;
            }
        }

        static string DisplayName(OwnedHeroProgression hero)
        {
            HeroKit kit;
            return HeroKitCatalog.TryGet(hero.HeroId, out kit) ? kit.DisplayName : hero.HeroId;
        }

        // ------------------------------------------------------------------
        // Detail
        // ------------------------------------------------------------------

        void OnCardSelected(string heroId)
        {
            _selectedHeroId = heroId;
            ShowDetail(SelectedHero);
            RefreshSelectionStates();
        }

        void RefreshSelectionStates()
        {
            for (int i = 0; i < _cards.Count; i++)
                _cards[i].SetSelected(
                    string.Equals(_selectedHeroId, _cards[i].HeroId, StringComparison.Ordinal));
        }

        void ShowDetail(OwnedHeroProgression hero)
        {
            if (hero == null)
            {
                _detailPanel.SetActive(false);
                return;
            }

            _detailPanel.SetActive(true);
            HeroKit kit;
            bool hasKit = HeroKitCatalog.TryGet(hero.HeroId, out kit);

            _detailName.text = hasKit ? kit.DisplayName : hero.HeroId;
            string rarityText = hero.Rarity.ToString().ToUpperInvariant();
            _detailMeta.text = hasKit
                ? string.Format("{0}  ·  {1}  ·  {2}  ·  Lv {3}",
                    rarityText, RoleLabel(kit.Role), RangeLabel(kit.Range), hero.Level)
                : string.Format("{0}  ·  Lv {1}", rarityText, hero.Level);

            int maxStars = StarProgressionRules.MaxStars(hero.Rarity);
            StarIconFactory.FillStarRow(_detailStarsRow, hero.Stars, maxStars,
                maxStars > 10 ? 30f : 38f, 6f);
            _detailStats.text = hasKit ? StatLine(kit) : string.Empty;

            Sprite portrait = HeroPortraitResolver.FindPortrait(hero.HeroId);
            _detailPortrait.sprite = portrait;
            _detailPortrait.color = portrait != null ? Color.white : new Color(1f, 1f, 1f, 0f);

            Sprite frame = PresentationVisuals.GetRarityFrame(hero.Rarity);
            _detailFrame.sprite = frame;
            _detailFrame.color = frame != null ? Color.white : new Color(1f, 1f, 1f, 0f);

            Sprite aura = ResolveEvolutionAura(hero);
            _detailAura.sprite = aura;
            _detailAura.color = aura != null ? new Color(1f, 1f, 1f, 0.55f) : new Color(1f, 1f, 1f, 0f);

            RebuildAbilities(kit);
            RefreshStarUpArea(hero);
        }

        static string StatLine(HeroKit kit)
        {
            // The kit exposes only the hero's scaling stat, not a concrete
            // stat block; surface it truthfully rather than fabricating values.
            return string.Format("Scaling stat: {0}", ScalingLabel(kit.Scaling));
        }

        void RebuildAbilities(HeroKit kit)
        {
            for (int i = _abilityList.childCount - 1; i >= 0; i--)
                Destroy(_abilityList.GetChild(i).gameObject);
            if (kit == null)
                return;

            for (int i = 0; i < kit.Abilities.Count; i++)
            {
                AbilityDefinition ability = kit.Abilities[i];
                RectTransform row = CreateRect(_abilityList, "Ability_" + ability.Slot);
                row.anchorMin = new Vector2(0f, 1f);
                row.anchorMax = new Vector2(1f, 1f);
                row.pivot = new Vector2(0.5f, 1f);
                float y = -i * 42f;
                row.offsetMin = new Vector2(0f, y - 38f);
                row.offsetMax = new Vector2(0f, y);

                var slot = CreateText(row, "Slot", SlotLabel(ability.Slot),
                    22, FontStyle.Bold, TextAnchor.MiddleLeft, AccentCyan);
                Anchor(slot.rectTransform, new Vector2(0f, 0f), new Vector2(0f, 1f),
                    new Vector2(0f, 0f), new Vector2(128f, 0f));

                var name = CreateText(row, "Name", ability.Name,
                    28, FontStyle.Normal, TextAnchor.MiddleLeft, TextPrimary);
                Anchor(name.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 1f),
                    new Vector2(136f, 0f), new Vector2(0f, 0f));
            }
        }

        void RefreshStarUpArea(OwnedHeroProgression hero)
        {
            StarUpRequirement req = StarProgressionRules.NextRequirement(hero.Rarity, hero.Stars);
            if (req == null)
            {
                _reqCopies.text = "—";
                _reqCopies.color = TextMuted;
                _reqFodder.text = "—";
                _reqFodder.color = TextMuted;
                _starUpLabel.text = "MAX STARS";
                _starUpState.text = "This hero has reached its rarity star cap.";
                SetButtonInteractable(_starUpButton, false);
                return;
            }

            _reqCopies.text = string.Format("{0} / {1}", hero.DuplicateCopies, req.DuplicateCopies);
            _reqCopies.color = hero.DuplicateCopies >= req.DuplicateCopies ? TextPrimary : DangerRed;
            _reqFodder.text = string.Format("{0} / {1}", hero.Fodder, req.Fodder);
            _reqFodder.color = hero.Fodder >= req.Fodder ? TextPrimary : DangerRed;

            bool canStarUp = hero.DuplicateCopies >= req.DuplicateCopies
                && hero.Fodder >= req.Fodder;
            _starUpLabel.text = string.Format("STAR UP  {0} > {1}", req.CurrentStars, req.NextStars);
            _starUpState.text = canStarUp
                ? NextStepHint(hero, req)
                : "Collect more duplicate copies and fodder.";
            SetButtonInteractable(_starUpButton, canStarUp);
        }

        static string NextStepHint(OwnedHeroProgression hero, StarUpRequirement req)
        {
            if (StarProgressionRules.IsApexCompletion(hero.Rarity, req.NextStars))
                return "Apex completion — final star.";
            if (StarProgressionRules.IsMajorEvolutionMilestone(hero.Rarity, req.NextStars))
                return "Major evolution milestone ahead.";
            return "Requirements met. Ready to star up.";
        }

        static void SetButtonInteractable(Button button, bool interactable)
        {
            button.interactable = interactable;
            var img = button.GetComponent<Image>();
            Color c = img.color;
            img.color = new Color(c.r, c.g, c.b, interactable ? 1f : 0.45f);
        }

        // ------------------------------------------------------------------
        // Star-up flow
        // ------------------------------------------------------------------

        void OnStarUpPressed()
        {
            OwnedHeroProgression hero = SelectedHero;
            if (hero == null)
                return;

            StarUpRequirement req = StarProgressionRules.NextRequirement(hero.Rarity, hero.Stars);
            if (req == null)
                return;

            int previousStars = hero.Stars;
            int copiesBefore = hero.DuplicateCopies;
            int fodderBefore = hero.Fodder;

            // Single authoritative domain call: TryStarUp validates resources
            // internally and mutates copies/fodder/stars exactly once on success.
            bool succeeded = hero.TryStarUp();
            if (!succeeded)
            {
                _starUpState.text = "Star-up failed — requirements not met.";
                RefreshStarUpArea(hero);
                return;
            }

            SaveState();
            ShowDetail(hero);
            RebuildRoster();
            RefreshSelectionStates();
            PlayCeremony(hero, previousStars, copiesBefore, fodderBefore);
        }

        void PlayCeremony(OwnedHeroProgression hero, int previousStars, int copiesBefore, int fodderBefore)
        {
            _ceremonyPanel.SetActive(true);
            var group = _ceremonyPanel.GetComponent<CanvasGroup>();
            group.alpha = 0f;
            group.blocksRaycasts = true;

            Sprite ceremony = PresentationVisuals.GetStarUpCeremony(hero.Rarity);
            _ceremonyImage.sprite = ceremony;
            _ceremonyImage.color = ceremony != null ? Color.white : new Color(1f, 1f, 1f, 0f);

            bool apex = StarProgressionRules.IsApexCompletion(hero.Rarity, hero.Stars);
            bool milestone = StarProgressionRules.IsMajorEvolutionMilestone(hero.Rarity, hero.Stars);
            _ceremonyText.text = apex ? "APEX AWAKENED" : milestone ? "EVOLUTION" : "STAR UP";

            HeroKit kit;
            string displayName = HeroKitCatalog.TryGet(hero.HeroId, out kit) ? kit.DisplayName : hero.HeroId;
            _ceremonySubText.text = string.Format(
                "{0}\n{1} > {2}\nCopies -{3}   ·   Fodder -{4}",
                displayName, previousStars, hero.Stars,
                copiesBefore - hero.DuplicateCopies,
                fodderBefore - hero.Fodder);

            float fadeIn = 0.4f;
            float hold = 1.2f;
            PresentationTimingConfig timing = PresentationVisuals.Timing;
            if (timing != null)
            {
                fadeIn = Mathf.Max(0.1f, timing.starUp.auraBuild);
                hold = Mathf.Max(0.2f, timing.starUp.starBurst + timing.starUp.statReveal);
            }

            if (_ceremonyRoutine != null)
                StopCoroutine(_ceremonyRoutine);
            _ceremonyRoutine = StartCoroutine(CeremonyFade(group, fadeIn, hold));
        }

        static IEnumerator CeremonyFade(CanvasGroup group, float fadeIn, float hold)
        {
            float t = 0f;
            while (t < fadeIn)
            {
                t += Time.unscaledDeltaTime;
                group.alpha = Mathf.Clamp01(t / fadeIn);
                yield return null;
            }
            group.alpha = 1f;

            float waited = 0f;
            while (waited < hold)
            {
                waited += Time.unscaledDeltaTime;
                yield return null;
            }
            // Panel stays up until the player taps CONTINUE.
        }

        void OnCeremonyClose()
        {
            if (_ceremonyRoutine != null)
            {
                StopCoroutine(_ceremonyRoutine);
                _ceremonyRoutine = null;
            }
            var group = _ceremonyPanel.GetComponent<CanvasGroup>();
            group.blocksRaycasts = false;
            _ceremonyPanel.SetActive(false);
        }

        void HandleSystemBack()
        {
            if (_navigatingAway)
                return;

            // The star-up ceremony is a modal overlay: back dismisses it first
            // instead of leaving the scene mid-presentation.
            if (_ceremonyPanel != null && _ceremonyPanel.activeSelf)
            {
                OnCeremonyClose();
                return;
            }

            OnBackPressed();
        }

        // ------------------------------------------------------------------
        // Controls / navigation
        // ------------------------------------------------------------------

        void CycleFilter()
        {
            _filter = (FilterMode)(((int)_filter + 1) % 5);
            RefreshControlLabels();
            RebuildRoster();
        }

        void CycleSort()
        {
            _sort = (SortMode)(((int)_sort + 1) % 4);
            RefreshControlLabels();
            RebuildRoster();
        }

        void RefreshControlLabels()
        {
            _filterLabel.text = "Filter: " + _filter.ToString().ToUpperInvariant();
            _sortLabel.text = "Sort: " + _sort.ToString().ToUpperInvariant();
        }

        static bool CanGoBack()
        {
            for (int i = 0; i < SceneManager.sceneCountInBuildSettings; i++)
            {
                string path = SceneUtility.GetScenePathByBuildIndex(i);
                if (path.EndsWith("/" + SceneKeys.MainMenuSceneKey + ".unity", StringComparison.Ordinal))
                    return true;
            }
            return false;
        }

        void OnBackPressed()
        {
            // Latch so a double press (button + system back in the same beat)
            // can never issue a duplicate scene load.
            if (_navigatingAway || !CanGoBack())
                return;
            _navigatingAway = true;
            SceneManager.LoadScene(SceneKeys.MainMenuSceneKey);
        }

        // ------------------------------------------------------------------
        // Visual helpers
        // ------------------------------------------------------------------

        Sprite ResolveEvolutionAura(OwnedHeroProgression hero)
        {
            // Aura art exists per faction x tier; the hero kit does not expose
            // faction, so try each curated faction for this hero's milestone tier.
            bool milestone = StarProgressionRules.IsMajorEvolutionMilestone(hero.Rarity, hero.Stars)
                || StarProgressionRules.IsApexCompletion(hero.Rarity, hero.Stars);
            if (!milestone)
                return null;

            for (int i = 0; i < GeneratedVisualKeys.FactionIds.Length; i++)
            {
                Sprite s = PresentationVisuals.GetEvolutionAura(GeneratedVisualKeys.FactionIds[i], hero.Stars);
                if (s != null)
                    return s;
            }
            return null;
        }

        static string RoleLabel(HeroRole role)
        {
            switch (role)
            {
                case HeroRole.Dps: return "DPS";
                case HeroRole.Defender: return "Defender";
                case HeroRole.Support: return "Support";
                default: return role.ToString();
            }
        }

        static string RangeLabel(RangeStyle range)
        {
            switch (range)
            {
                case RangeStyle.Melee: return "Melee";
                case RangeStyle.Long: return "Long range";
                default: return range.ToString();
            }
        }

        static string ScalingLabel(ScalingStat stat)
        {
            switch (stat)
            {
                case ScalingStat.Attack: return "ATK";
                case ScalingStat.Magic: return "MAG";
                case ScalingStat.MaxHealth: return "HP";
                case ScalingStat.Defense: return "DEF";
                default: return stat.ToString();
            }
        }

        static string SlotLabel(AbilitySlot slot)
        {
            switch (slot)
            {
                case AbilitySlot.Basic: return "BASIC";
                case AbilitySlot.Skill: return "SKILL";
                case AbilitySlot.Passive: return "PASSIVE";
                case AbilitySlot.Ultimate: return "ULT";
                default: return slot.ToString().ToUpperInvariant();
            }
        }

        // ------------------------------------------------------------------
        // UI construction helpers
        // ------------------------------------------------------------------

        static RectTransform CreateRect(Transform parent, string name)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            return (RectTransform)go.transform;
        }

        static Image CreateImage(Transform parent, string name, Color color)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            var img = go.GetComponent<Image>();
            img.color = color;
            return img;
        }

        Text CreateText(Transform parent, string name, string content, int size,
            FontStyle style, TextAnchor anchor, Color color)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Text));
            go.transform.SetParent(parent, false);
            var text = go.GetComponent<Text>();
            text.font = _font;
            text.text = content;
            text.fontSize = size;
            text.fontStyle = style;
            text.alignment = anchor;
            text.color = color;
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            text.verticalOverflow = VerticalWrapMode.Overflow;
            text.raycastTarget = false;
            return text;
        }

        Button CreateButton(Transform parent, string name, string label, int fontSize,
            UnityEngine.Events.UnityAction onClick)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            Text text = CreateText(go.transform, "Label", label,
                fontSize, FontStyle.Normal, TextAnchor.MiddleCenter, TextPrimary);
            Stretch(text.rectTransform);
            var btn = go.GetComponent<Button>();
            btn.targetGraphic = go.GetComponent<Image>();
            if (onClick != null)
                btn.onClick.AddListener(onClick);
            var colors = btn.colors;
            colors.highlightedColor = new Color(1.15f, 1.15f, 1.2f);
            colors.pressedColor = new Color(0.8f, 0.8f, 0.9f);
            btn.colors = colors;
            return btn;
        }

        static void StyleButton(Button button, Color bg, Color labelColor)
        {
            button.GetComponent<Image>().color = bg;
            var label = button.GetComponentInChildren<Text>();
            if (label != null)
                label.color = labelColor;
        }

        static void Stretch(RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
        }

        static void Anchor(RectTransform rt, Vector2 min, Vector2 max,
            Vector2 offsetMin, Vector2 offsetMax)
        {
            rt.anchorMin = min;
            rt.anchorMax = max;
            rt.offsetMin = offsetMin;
            rt.offsetMax = offsetMax;
        }
    }
}
