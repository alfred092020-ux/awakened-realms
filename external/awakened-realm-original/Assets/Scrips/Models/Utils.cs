using System;
using System.Collections.Generic;
using Cysharp.Threading.Tasks;
using Unity.VisualScripting.Antlr3.Runtime.Misc;
using UnityEngine;
using UnityEngine.UI;

namespace AwakenedRealm.Models
{
    public class Utils
    {
        public static async UniTask FadeBackground(
            float targetAlpha,
            float duration,
            Image img)
        {
            if (img == null)
                return;

            Color startColor = img.color;
            float startAlpha = startColor.a;
            float elapsed = 0f;

            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float t = elapsed / duration;

                float alpha = Mathf.Lerp(startAlpha, targetAlpha, t);
                img.color = new Color(
                    startColor.r,
                    startColor.g,
                    startColor.b,
                    alpha
                );
            }

            // ensure final value
            img.color = new Color(
                startColor.r,
                startColor.g,
                startColor.b,
                targetAlpha
            );
        }
    }

    public static class Gameplay
    {
        public static float MaxHealth = 1000f;
        public static float NaxAttack = 1000f;
        public static float MaxDefence = 1000f;
        public static float MaxMagic = 1000f;
        public static float MaxCritic = 1000f;
        public static float MaxResistance = 1000f;
        public static float MaxSpeed = 1000f;


        /// <summary>
        /// Return the same stats but with the added values
        /// </summary>
        /// <param name="stats"></param>
        /// <returns></returns>
        public static void IncreaseStats(HeroStats stats, float additionValue)
        {
            stats.ATK += additionValue;
            stats.CRIT += additionValue;
            stats.Health += additionValue;
            stats.SPD += additionValue;
            stats.RES += additionValue;
            stats.DEF += additionValue;
            stats.Health += additionValue;
        }

        /// <summary>
        /// Return the same stats but with the multiplied values
        /// </summary>
        /// <param name="stats"></param>
        /// <returns></returns>

        public static void MultiplyStats(HeroStats stats, float multipliedValue)
        {
            stats.ATK *= multipliedValue;
            stats.CRIT *= multipliedValue;
            stats.Health *= multipliedValue;
            stats.SPD *= multipliedValue;
            stats.RES *= multipliedValue;
            stats.DEF *= multipliedValue;
            stats.Health *= multipliedValue;
        }
    }

    public static class JsonHelper
    {
        public static T FromJson<T>(string json)
        {
            if (string.IsNullOrEmpty(json))
            {
                Debug.LogWarning("JsonHelper.ToJson: JSON string is null or empty.");
                return default;
            }

            return JsonUtility.FromJson<T>(json);
        }

        public static List<T> FromJsonList<T>(string json)
        {
            if (string.IsNullOrEmpty(json))
            {
                Debug.LogWarning("JsonHelper.ToJsonList: JSON string is null or empty.");
                return new List<T>();
            }

            Wrapper<T> wrapper = JsonUtility.FromJson<Wrapper<T>>(json);
            return new List<T>(wrapper.items);
        }

        public static string ToJson<T>(T obj, bool prettyPrint = false)
        {
            if (obj == null)
            {
                Debug.LogWarning("JsonHelper.FromJson: Object is null.");
                return string.Empty;
            }

            return JsonUtility.ToJson(obj, prettyPrint);
        }

        public static string ToJsonList<T>(List<T> list, bool prettyPrint = false)
        {
            if (list == null || list.Count == 0)
            {
                Debug.LogWarning("JsonHelper.FromJsonList: List is null or empty.");
                return "[]";
            }

            Wrapper<T> wrapper = new Wrapper<T> { items = list.ToArray() };
            return JsonUtility.ToJson(wrapper, prettyPrint);
        }

        [Serializable]
        private class Wrapper<T>
        {
            public T[] items;
        }
    }



}