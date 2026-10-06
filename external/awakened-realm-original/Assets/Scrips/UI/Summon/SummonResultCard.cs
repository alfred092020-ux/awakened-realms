using AwakenedRealm.Enums;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.UI.Summon
{
    /// <summary>
    /// Compact result tile for a single resolved pull in the multi-summon grid.
    /// Presentational only — everything displayed is passed in from the actual
    /// SummonPullResult data.
    /// </summary>
    public sealed class SummonResultCard : MonoBehaviour
    {
        [SerializeField] CanvasGroup _canvasGroup;
        [SerializeField] Image _frameImage;
        [SerializeField] Image _portraitImage;
        [SerializeField] TMP_Text _nameText;
        [SerializeField] TMP_Text _outcomeText;
        [SerializeField] Image _accentBarImage;

        public void Bind(Sprite portrait, string heroName, HeroRarity rarity,
            bool isNew, int duplicateCopies, Color rarityColor, Sprite frame)
        {
            if (_frameImage != null)
            {
                _frameImage.enabled = true;
                if (frame != null)
                {
                    _frameImage.sprite = frame;
                    _frameImage.color = Color.white;
                }
                else
                {
                    // Frame art is optional presentation; fall back to a tint.
                    _frameImage.sprite = null;
                    _frameImage.color = new Color(rarityColor.r, rarityColor.g, rarityColor.b, 0.35f);
                }
            }

            if (_portraitImage != null)
            {
                if (portrait != null)
                {
                    _portraitImage.sprite = portrait;
                    _portraitImage.enabled = true;
                    _portraitImage.preserveAspect = true;
                }
                else
                {
                    _portraitImage.enabled = false;
                }
            }

            if (_nameText != null)
                _nameText.text = string.IsNullOrEmpty(heroName) ? "Unknown Hero" : heroName;

            if (_outcomeText != null)
            {
                _outcomeText.text = isNew ? "NEW" : "DUP x" + duplicateCopies;
                _outcomeText.color = isNew ? rarityColor : new Color(0.85f, 0.85f, 0.9f);
            }

            if (_accentBarImage != null)
                _accentBarImage.color = rarityColor;
        }

        public void SetAlpha(float alpha)
        {
            if (_canvasGroup == null)
                _canvasGroup = GetComponent<CanvasGroup>();
            if (_canvasGroup != null)
                _canvasGroup.alpha = alpha;
        }
    }
}
