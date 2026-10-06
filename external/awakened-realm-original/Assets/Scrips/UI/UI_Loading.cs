using System;
using System.Threading;
using AwakenedRealm.Models;
using Cysharp.Threading.Tasks;
using TMPro;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_Loading : MonoBehaviour
    {
        [SerializeField] private UI_Slide _slideUI;
        [SerializeField] private TMP_Text _loadingText;
        [SerializeField] private Image _backgroundImg;

        [SerializeField] private bool _undoOnStart;


        private void Start()
        {
            if (_undoOnStart)
            {
                SetUI_Text("");
                SetUI_LoadingAnimation(false);
            }
        }

        public async void SetUI_Text(string loadingMsg)
        {
            _loadingText.text = loadingMsg;
        }

        public async void SetUI_LoadingAnimation(bool isEnabled)
        {
            _backgroundImg.raycastTarget = isEnabled;
            
            if (isEnabled)
            {
                Utils.FadeBackground(0.75f, .25f, _backgroundImg);
                _slideUI.Execute();
            }
            else
            {
                Utils.FadeBackground(0.0f, .25f, _backgroundImg);
                _slideUI.Undo();
            }
        }

        // public async UniTask FadeBackground(
        //     float targetAlpha,
        //     float duration = 0.3f,
        //     CancellationToken cancellationToken = default)
        // {
        //     if (_backgroundImg == null)
        //         return;
        //
        //     Color startColor = _backgroundImg.color;
        //     float startAlpha = startColor.a;
        //     float elapsed = 0f;
        //
        //     while (elapsed < duration)
        //     {
        //         if (cancellationToken.IsCancellationRequested)
        //             return;
        //
        //         elapsed += Time.deltaTime;
        //         float t = elapsed / duration;
        //
        //         float alpha = Mathf.Lerp(startAlpha, targetAlpha, t);
        //         _backgroundImg.color = new Color(
        //             startColor.r,
        //             startColor.g,
        //             startColor.b,
        //             alpha
        //         );
        //
        //         await UniTask.Yield(PlayerLoopTiming.Update, cancellationToken);
        //     }
        //
        //     // ensure final value
        //     _backgroundImg.color = new Color(
        //         startColor.r,
        //         startColor.g,
        //         startColor.b,
        //         targetAlpha
        //     );
        // }
    }
}