using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using AwakenedRealm.CombatV2;
using AwakenedRealm.Data;
using AwakenedRealm.Enums;
using AwakenedRealm.Keys;
using AwakenedRealm.Models;
using AwakenedRealm.Persistence;
using AwakenedRealm.Presentation;
using AwakenedRealm.Progression;
using AwakenedRealm.Scriptables;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace AwakenedRealm.UI.Summon
{
    /// <summary>
    /// Summon chamber screen. All result processing, spending, pity, duplicate
    /// handling, and persistence go through the existing deterministic domain
    /// (<see cref="SummonExecutor"/> + <see cref="ProgressionSave"/>); this class
    /// is presentation-only and never rolls or mutates anything itself.
    /// </summary>
    public sealed class SummonScreen : MonoBehaviour
    {
        [Header("Chamber")]
        [SerializeField] Image _backgroundImage;
        [SerializeField] Image _portalImage;
        [SerializeField] RectTransform _portalRect;
        [SerializeField] CanvasGroup _portalGroup;

        [Header("Header")]
        [SerializeField] TMPro.TMP_Text _ticketsValueText;
        [SerializeField] TMPro.TMP_Text _gemsValueText;
        [SerializeField] TMPro.TMP_Text _pityValueText;

        [Header("Buttons")]
        [SerializeField] Button _backButton;
        [SerializeField] Button _summonSingleButton;
        [SerializeField] Button _summonTenButton;
        [SerializeField] TMPro.TMP_Text _summonSingleCostText;
        [SerializeField] TMPro.TMP_Text _summonTenCostText;

        [Header("Status")]
        [SerializeField] GameObject _statusPanel;
        [SerializeField] TMPro.TMP_Text _statusText;

        [Header("Reveal Overlay")]
        [SerializeField] GameObject _revealOverlay;
        [SerializeField] Image _revealDimImage;
        [SerializeField] Image _revealFlashImage;
        [SerializeField] Image _revealPortalImage;
        [SerializeField] RectTransform _revealPortalRect;
        [SerializeField] Image _revealArtImage;
        [SerializeField] RectTransform _revealArtRect;
        [SerializeField] CanvasGroup _revealArtGroup;
        [SerializeField] TMPro.TMP_Text _revealRarityText;
        [SerializeField] CanvasGroup _revealRarityGroup;

        [Header("Single Result")]
        [SerializeField] CanvasGroup _singleResultGroup;
        [SerializeField] Image _singleHeroImage;
        [SerializeField] TMPro.TMP_Text _singleNameText;
        [SerializeField] TMPro.TMP_Text _singleRarityText;
        [SerializeField] TMPro.TMP_Text _singleOutcomeText;

        [Header("Multi Result")]
        [SerializeField] CanvasGroup _multiResultGroup;
        [SerializeField] Transform _multiGridContent;
        [SerializeField] SummonResultCard _resultCardPrefab;
        [SerializeField] Button _continueButton;

        SummonHeroPool _domainPool;
        SummonConfig _config;
        GameProgressionState _state;
        IDeterministicRandom _rng;

        bool _initialized;
        bool _summonInFlight;
        bool _navigatingAway;
        Coroutine _revealRoutine;

        void Awake()
        {
            SetInitialUiState();
            InitializeDomain();
        }

        void Start()
        {
            ApplyArtDirection();
            WireButtons();
            RefreshHeader();
            RefreshCosts();
        }

        void OnDestroy()
        {
            // Persist once more on exit so a killed reveal never loses a
            // successfully committed transaction.
            TrySaveState();
        }

        void Update()
        {
            // Android system back maps to Escape; route it through the same
            // guarded path as the visible Back button so an in-flight
            // summon/reveal still blocks leaving.
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                OnBackClicked();
                return;
            }

            // Gentle idle motion on the chamber portal; frozen during a reveal.
            if (_summonInFlight)
                return;
            if (_portalRect != null)
                _portalRect.Rotate(0f, 0f, -9f * Time.deltaTime);
            if (_portalGroup != null)
                _portalGroup.alpha = 0.85f + 0.15f * Mathf.Sin(Time.time * 1.4f);
        }

        void SetInitialUiState()
        {
            if (_revealOverlay != null) _revealOverlay.SetActive(false);
            if (_statusPanel != null) _statusPanel.SetActive(false);
            if (_portalGroup != null) _portalGroup.alpha = 1f;
        }

        void InitializeDomain()
        {
            _config = new SummonConfig();
            try
            {
                // The summon pool is sourced from the existing canon hero kit
                // catalog — real stable IDs and authored rarities, nothing
                // fabricated. The domain pool validates all-or-nothing.
                var entries = new List<SummonPoolEntry>(HeroKitCatalog.Count);
                for (int i = 0; i < HeroKitCatalog.Count; i++)
                {
                    HeroKit kit = HeroKitCatalog.All[i];
                    HeroRarity rarity;
                    if (!TryParseRarity(kit.Rarity, out rarity))
                        throw new InvalidOperationException("Hero kit has unsupported rarity: " + kit.Id);
                    entries.Add(new SummonPoolEntry(kit.Id, rarity));
                }

                _domainPool = new SummonHeroPool(entries);
                // No allowlist on load: a roster may legitimately hold heroes
                // that are not in this banner's pool, and the domain validates
                // record integrity on its own.
                _state = ProgressionSave.LoadState();
                // The presentation layer does not own the RNG stream; it derives
                // a fresh unpredictable seed per session and hands it to the
                // domain's deterministic RNG implementation.
                _rng = new XorShift64Random(GenerateSeed());
                _initialized = true;
            }
            catch (Exception ex)
            {
                Debug.LogError("[SummonScreen] Summon domain init failed: " + ex.Message);
                ShowStatus("The summoning chamber is sealed for now.\n" + ex.Message);
                SetSummonButtonsInteractable(false);
                _initialized = false;
            }
        }

        static bool TryParseRarity(string rarity, out HeroRarity result)
        {
            result = HeroRarity.rare;
            if (string.IsNullOrWhiteSpace(rarity))
                return false;
            switch (rarity.Trim().ToLowerInvariant())
            {
                case "rare": result = HeroRarity.rare; return true;
                case "epic": result = HeroRarity.epic; return true;
                case "legendary": result = HeroRarity.legendary; return true;
                case "mythic": result = HeroRarity.mythic; return true;
                default: return false;
            }
        }

        static ulong GenerateSeed()
        {
            byte[] bytes = new byte[8];
            using (var rng = new RNGCryptoServiceProvider())
                rng.GetBytes(bytes);
            ulong seed = BitConverter.ToUInt64(bytes, 0);
            return seed == 0 ? 0x9E3779B97F4A7C15UL : seed;
        }

        void ApplyArtDirection()
        {
            if (_backgroundImage != null)
            {
                Sprite bg = PresentationVisuals.GetSummon();
                if (bg != null) _backgroundImage.sprite = bg;
            }

            // Idle portal hints at the common tier; the real rarity art is only
            // picked once results exist, inside the reveal sequence.
            if (_portalImage != null)
            {
                Sprite portal = PresentationVisuals.GetSummonPortal(HeroRarity.rare);
                if (portal != null)
                {
                    _portalImage.sprite = portal;
                    _portalImage.enabled = true;
                }
            }
        }

        void WireButtons()
        {
            if (_backButton != null) _backButton.onClick.AddListener(OnBackClicked);
            if (_summonSingleButton != null) _summonSingleButton.onClick.AddListener(OnSummonSingleClicked);
            if (_summonTenButton != null) _summonTenButton.onClick.AddListener(OnSummonTenClicked);
            if (_continueButton != null) _continueButton.onClick.AddListener(OnContinueClicked);
        }

        // ------------------------------------------------------------------
        // Header / costs — only real persisted values are ever displayed.
        // ------------------------------------------------------------------

        void RefreshHeader()
        {
            if (_state == null) return;
            if (_ticketsValueText != null)
                _ticketsValueText.text = _state.SummonTickets.ToString(CultureInfo.InvariantCulture);
            if (_gemsValueText != null)
                _gemsValueText.text = _state.Gems.ToString(CultureInfo.InvariantCulture);
            if (_pityValueText != null)
                _pityValueText.text = string.Format(CultureInfo.InvariantCulture,
                    "{0}/{1}  ·  {2}/{3}",
                    _state.LegendaryPity, SummoningService.LegendaryHardPity,
                    _state.MythicPity, SummoningService.MythicHardPity);
        }

        void RefreshCosts()
        {
            if (_config == null) return;
            if (_summonSingleCostText != null)
                _summonSingleCostText.text = string.Format(CultureInfo.InvariantCulture,
                    "{0} ticket or {1} gems", _config.TicketCostSingle, _config.GemCostSingle);
            if (_summonTenCostText != null)
                _summonTenCostText.text = string.Format(CultureInfo.InvariantCulture,
                    "{0} tickets or {1} gems  ·  Epic+ guaranteed", _config.TicketCostTenPull, _config.GemCostTenPull);
        }

        void SetSummonButtonsInteractable(bool interactable)
        {
            if (_summonSingleButton != null) _summonSingleButton.interactable = interactable;
            if (_summonTenButton != null) _summonTenButton.interactable = interactable;
        }

        void ShowStatus(string message)
        {
            if (_statusPanel != null) _statusPanel.SetActive(true);
            if (_statusText != null) _statusText.text = message;
        }

        void HideStatus()
        {
            if (_statusPanel != null) _statusPanel.SetActive(false);
        }

        // ------------------------------------------------------------------
        // Summon actions — one domain call per intended request, exactly once.
        // ------------------------------------------------------------------

        void OnSummonSingleClicked()
        {
            TrySummon(tenPull: false);
        }

        void OnSummonTenClicked()
        {
            TrySummon(tenPull: true);
        }

        void TrySummon(bool tenPull)
        {
            if (!_initialized || _summonInFlight)
                return;

            _summonInFlight = true;
            SetSummonButtonsInteractable(false);

            SummonResult result;
            try
            {
                result = tenPull
                    ? SummonExecutor.SummonTenPull(_state, _domainPool, _rng, _config)
                    : SummonExecutor.SummonSingle(_state, _domainPool, _rng, _config);
            }
            catch (Exception ex)
            {
                // Domain threw before commit (e.g. insufficient resources);
                // state is untouched, so simply re-enable and tell the player.
                _summonInFlight = false;
                SetSummonButtonsInteractable(true);
                ShowStatus(ex.Message);
                return;
            }

            // The executor already committed roster, wallet, and pity atomically.
            TrySaveState();
            RefreshHeader();
            HideStatus();

            _revealRoutine = StartCoroutine(PlayRevealSequence(result));
        }

        void TrySaveState()
        {
            if (_state == null) return;
            try
            {
                ProgressionSave.SaveState(_state);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[SummonScreen] Save failed: " + ex.Message);
            }
        }

        // ------------------------------------------------------------------
        // Reveal presentation — driven entirely by the returned rarities.
        // ------------------------------------------------------------------

        IEnumerator PlayRevealSequence(SummonResult result)
        {
            OpenRevealOverlay();

            float portalIdle = Timing(s => s.portalIdle, 1.2f);
            float rarityReveal = Timing(s => s.rarityReveal, 0.9f);
            float heroReveal = Timing(s => s.heroReveal, 0.8f);
            float linger = Timing(s => s.resultLinger, 1f);

            HideResultGroups();
            yield return PortalCharge(result.Pulls.Count > 1
                ? HighestRarity(result.Pulls)
                : result.Pulls[0].Rarity, portalIdle, rarityReveal);

            if (result.Pulls.Count == 1)
            {
                yield return RevealSingle(result.Pulls[0], heroReveal);
                yield return new WaitForSeconds(linger);
            }
            else
            {
                yield return RevealMulti(result.Pulls, heroReveal);
            }

            if (_continueButton != null) _continueButton.gameObject.SetActive(true);
            _revealRoutine = null;
        }

        static HeroRarity HighestRarity(List<SummonPullResult> pulls)
        {
            HeroRarity best = HeroRarity.rare;
            for (int i = 0; i < pulls.Count; i++)
                if (pulls[i].Rarity > best)
                    best = pulls[i].Rarity;
            return best;
        }

        float Timing(Func<PresentationTimingConfig.SummonTimings, float> pick, float fallback)
        {
            var cfg = PresentationVisuals.Timing;
            if (cfg == null || cfg.summon == null) return fallback;
            float v = pick(cfg.summon);
            return v > 0f ? v : fallback;
        }

        void OpenRevealOverlay()
        {
            if (_revealOverlay != null) _revealOverlay.SetActive(true);
            if (_revealDimImage != null)
            {
                Color c = _revealDimImage.color;
                c.a = 0f;
                _revealDimImage.color = c;
            }
            if (_revealFlashImage != null)
            {
                Color c = _revealFlashImage.color;
                c.a = 0f;
                _revealFlashImage.color = c;
                _revealFlashImage.gameObject.SetActive(true);
            }
            if (_continueButton != null) _continueButton.gameObject.SetActive(false);
        }

        IEnumerator PortalCharge(HeroRarity peakRarity, float idleDuration, float burstDuration)
        {
            // Portal art always reflects the actual result rarity.
            Sprite portal = PresentationVisuals.GetSummonPortal(peakRarity);
            if (_revealPortalImage != null)
            {
                if (portal != null)
                {
                    _revealPortalImage.sprite = portal;
                    _revealPortalImage.enabled = true;
                }
                else
                {
                    _revealPortalImage.enabled = false;
                }
            }

            Color rarityColor = RarityColor(peakRarity);
            if (_revealRarityText != null)
            {
                _revealRarityText.text = peakRarity.ToString().ToUpperInvariant();
                _revealRarityText.color = rarityColor;
            }
            if (_revealRarityGroup != null) _revealRarityGroup.alpha = 0f;
            if (_revealArtGroup != null) _revealArtGroup.alpha = 0f;

            // Dim in.
            yield return FadeImage(_revealDimImage, 0f, 0.85f, 0.25f);

            // Portal spins up.
            if (_revealPortalRect != null)
            {
                _revealPortalRect.localScale = Vector3.one * 0.3f;
                float elapsed = 0f;
                Quaternion start = _revealPortalRect.localRotation;
                while (elapsed < idleDuration)
                {
                    elapsed += Time.deltaTime;
                    float t = Mathf.Clamp01(elapsed / idleDuration);
                    _revealPortalRect.localScale = Vector3.one * Mathf.Lerp(0.3f, 1f, EaseOutCubic(t));
                    _revealPortalRect.localRotation = start * Quaternion.Euler(0f, 0f, -360f * t);
                    yield return null;
                }
                _revealPortalRect.localScale = Vector3.one;
                _revealPortalRect.localRotation = start;
            }
            else
            {
                yield return new WaitForSeconds(idleDuration);
            }

            // Rarity flash + label.
            if (_revealFlashImage != null)
            {
                Color c = rarityColor;
                _revealFlashImage.color = c;
                yield return FadeImage(_revealFlashImage, 0f, 0.95f, burstDuration * 0.5f);
            }
            if (_revealRarityGroup != null)
                yield return FadeGroup(_revealRarityGroup, 0f, 1f, 0.2f);
            if (_revealFlashImage != null)
                yield return FadeImage(_revealFlashImage, 0.95f, 0f, burstDuration * 0.5f);
        }

        IEnumerator RevealSingle(SummonPullResult pull, float heroReveal)
        {
            Sprite revealArt = PresentationVisuals.GetSummonReveal(pull.Rarity);
            if (_revealArtImage != null)
            {
                if (revealArt != null)
                {
                    _revealArtImage.sprite = revealArt;
                    _revealArtImage.enabled = true;
                }
                else
                {
                    _revealArtImage.enabled = false;
                }
            }

            // Rarity art blooms behind the hero card before the result details.
            if (_revealArtGroup != null)
                yield return FadeGroup(_revealArtGroup, 0f, 0.9f, heroReveal * 0.5f);

            HeroSO heroSo = ResolveHero(pull.HeroId);
            Sprite heroSprite = heroSo != null ? heroSo.GetHeroSprite() : null;
            if (_singleHeroImage != null)
            {
                _singleHeroImage.sprite = heroSprite != null ? heroSprite : revealArt;
                _singleHeroImage.enabled = _singleHeroImage.sprite != null;
                _singleHeroImage.preserveAspect = true;
            }

            if (_singleNameText != null)
                _singleNameText.text = ResolveDisplayName(pull.HeroId, heroSo);
            if (_singleRarityText != null)
            {
                _singleRarityText.text = pull.Rarity.ToString().ToUpperInvariant();
                _singleRarityText.color = RarityColor(pull.Rarity);
            }
            if (_singleOutcomeText != null)
                _singleOutcomeText.text = pull.IsNew
                    ? "NEW HERO"
                    : string.Format(CultureInfo.InvariantCulture, "DUPLICATE  ·  {0} copies", pull.ResultingDuplicateCopies);

            if (_singleResultGroup != null)
            {
                _singleResultGroup.gameObject.SetActive(true);
                yield return FadeGroup(_singleResultGroup, 0f, 1f, heroReveal);
            }
        }

        IEnumerator RevealMulti(List<SummonPullResult> pulls, float heroReveal)
        {
            if (_multiResultGroup != null)
            {
                _multiResultGroup.gameObject.SetActive(true);
                _multiResultGroup.alpha = 1f;
            }

            if (_multiGridContent == null || _resultCardPrefab == null)
                yield break;

            // Clear leftovers.
            for (int i = _multiGridContent.childCount - 1; i >= 0; i--)
                Destroy(_multiGridContent.GetChild(i).gameObject);

            var cards = new List<SummonResultCard>(pulls.Count);
            for (int i = 0; i < pulls.Count; i++)
            {
                SummonPullResult pull = pulls[i];
                HeroSO heroSo = ResolveHero(pull.HeroId);
                SummonResultCard card = Instantiate(_resultCardPrefab, _multiGridContent);
                card.gameObject.SetActive(true);
                card.Bind(
                    portrait: heroSo != null ? heroSo.GetHeroSprite() : null,
                    heroName: ResolveDisplayName(pull.HeroId, heroSo),
                    rarity: pull.Rarity,
                    isNew: pull.IsNew,
                    duplicateCopies: pull.ResultingDuplicateCopies,
                    rarityColor: RarityColor(pull.Rarity),
                    frame: PresentationVisuals.GetRarityFrame(pull.Rarity));
                card.SetAlpha(0f);
                cards.Add(card);
            }

            // Staggered reveal keeps 10 results readable on small screens.
            float stagger = Mathf.Clamp(heroReveal * 0.25f, 0.03f, 0.12f);
            float fade = Mathf.Clamp(heroReveal * 0.5f, 0.15f, 0.4f);
            for (int i = 0; i < cards.Count; i++)
            {
                StartCoroutine(FadeCard(cards[i], fade));
                yield return new WaitForSeconds(stagger);
            }
            yield return new WaitForSeconds(fade);
        }

        IEnumerator FadeCard(SummonResultCard card, float duration)
        {
            float elapsed = 0f;
            while (elapsed < duration && card != null)
            {
                elapsed += Time.deltaTime;
                card.SetAlpha(Mathf.Clamp01(elapsed / duration));
                yield return null;
            }
            if (card != null) card.SetAlpha(1f);
        }

        void HideResultGroups()
        {
            if (_singleResultGroup != null)
            {
                _singleResultGroup.alpha = 0f;
                _singleResultGroup.gameObject.SetActive(false);
            }
            if (_multiResultGroup != null)
            {
                _multiResultGroup.alpha = 0f;
                _multiResultGroup.gameObject.SetActive(false);
            }
        }

        void OnContinueClicked()
        {
            if (_summonInFlight)
            {
                _summonInFlight = false;
                SetSummonButtonsInteractable(true);
            }
            if (_revealRoutine != null)
            {
                StopCoroutine(_revealRoutine);
                _revealRoutine = null;
            }
            if (_revealOverlay != null) _revealOverlay.SetActive(false);
            HideResultGroups();
        }

        void OnBackClicked()
        {
            // Block leaving mid-transaction; the reveal is visual only, but
            // keeping the screen alive until it ends avoids any ambiguity.
            if (_summonInFlight) return;

            // Latch so repeated visible/system back presses in the same or
            // following frames cannot enqueue MainMenu twice.
            if (_navigatingAway) return;

            TrySaveState();
            if (Application.CanStreamedLevelBeLoaded(SceneKeys.MainMenuSceneKey))
            {
                _navigatingAway = true;
                if (_backButton != null) _backButton.interactable = false;
                SceneManager.LoadScene(SceneKeys.MainMenuSceneKey);
            }
            else
            {
                ShowStatus("MainMenu scene is not available in this build.");
            }
        }

        // ------------------------------------------------------------------
        // Helpers
        // ------------------------------------------------------------------

        HeroSO ResolveHero(string heroId)
        {
            // Optional portrait lookup only; kit-catalog heroes are not part of
            // the legacy HeroSO collection, so null is a normal outcome.
            if (string.IsNullOrEmpty(heroId))
                return null;
            var data = ReusableData.Instance;
            if (data == null)
                return null;
            HeroSOCollection collection = data.GetHeroSOCollection();
            return collection != null ? collection.GetHeroByID(heroId) : null;
        }

        static string ResolveDisplayName(string heroId, HeroSO heroSo)
        {
            // Prefer the authored display name from the hero kit catalog — the
            // pool is built from it, so an entry always exists. HeroSO is only
            // a portrait fallback and may carry a different naming scheme.
            HeroKit kit;
            if (HeroKitCatalog.TryGet(heroId, out kit) && !string.IsNullOrWhiteSpace(kit.DisplayName))
                return kit.DisplayName;
            HeroProfile profile = heroSo != null ? heroSo.GetHeroProfile() : null;
            if (profile != null && !string.IsNullOrWhiteSpace(profile.HeroName))
                return profile.HeroName;
            return heroId;
        }

        static Color RarityColor(HeroRarity rarity)
        {
            switch (rarity)
            {
                case HeroRarity.mythic: return new Color(1f, 0.35f, 0.55f);
                case HeroRarity.legendary: return new Color(1f, 0.78f, 0.25f);
                case HeroRarity.epic: return new Color(0.65f, 0.45f, 1f);
                case HeroRarity.rare:
                default: return new Color(0.4f, 0.75f, 1f);
            }
        }

        static float EaseOutCubic(float t)
        {
            float inv = 1f - t;
            return 1f - inv * inv * inv;
        }

        IEnumerator FadeImage(Image image, float from, float to, float duration)
        {
            if (image == null || duration <= 0f) yield break;
            float elapsed = 0f;
            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float a = Mathf.Lerp(from, to, Mathf.Clamp01(elapsed / duration));
                Color c = image.color;
                c.a = a;
                image.color = c;
                yield return null;
            }
            Color final = image.color;
            final.a = to;
            image.color = final;
        }

        IEnumerator FadeGroup(CanvasGroup group, float from, float to, float duration)
        {
            if (group == null || duration <= 0f)
            {
                if (group != null) group.alpha = to;
                yield break;
            }
            float elapsed = 0f;
            group.alpha = from;
            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                group.alpha = Mathf.Lerp(from, to, Mathf.Clamp01(elapsed / duration));
                yield return null;
            }
            group.alpha = to;
        }
    }
}
