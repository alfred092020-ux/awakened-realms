using UnityEngine;
using TMPro;
using UnityEngine.UI;
using AwakenedRealm.Models;

namespace AwakenedRealm
{
    public class HeroCanvas : MonoBehaviour
    {
        [SerializeField] TMP_Text _heroNameText;
        [SerializeField] Image _healthBar;
        [SerializeField] Image _magicPowerBar;  // mana

        // 🔒 Private health data
        float _maxHealth;
        float _currentHealth;

        // Sets the hero name on the canvas
        public void SetHeroName(string name)
        {
            _heroNameText.text = name;
        }

        /// <summary>
        /// Sets TOTAL health (could be 1000, 500, 200, etc.)
        /// </summary>
        public void SetHealth(float health)
        {
            _maxHealth = health;                // Set max health
            _currentHealth = health;            // Set current health to max at the start
            _healthBar.fillAmount = 1f;         // Fill bar to 100% initially
        }

        /// <summary>
        /// Decreases health based on attacker attack value
        /// </summary>
        public void DecreaseAmount(float attack)
        {
            // Decrease current health by attack value
            _currentHealth -= attack;

            // Clamp health between 0 and max
            _currentHealth = Mathf.Clamp(_currentHealth, 0f, _maxHealth);

            // Calculate the new fill amount (current health / max health)
            _healthBar.fillAmount = _currentHealth / _maxHealth;
        }

        public void SetMagicPower(float magicPower)
        {
            float fillAmount = Mathf.Clamp01(magicPower / Gameplay.MaxMagic);
            _magicPowerBar.fillAmount = fillAmount;
        }

        public void ResetBars()
        {
            _healthBar.fillAmount = 1f;
            _magicPowerBar.fillAmount = 1f;
        }

        public float GetCurrentHealth() => _currentHealth;
    }
}
