using System.Threading.Tasks;
using DG.Tweening;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace AwakenedRealm.UI
{
    public class UI_Scale : MonoBehaviour
    {
        [Header("Scale Settings")]
        public Vector3 scaleUp = new Vector3(1.2f, 1.2f, 1.2f);
        public Vector3 scaleDown = new Vector3(1f, 1f, 1f);
        public float duration = 0.5f;

        [Header("Loop Settings")]
        public LoopType loopType = LoopType.Yoyo;
        public int loops = -1; // -1 for infinite loops

        [Header("Ease Settings")]
        public Ease easeType = Ease.InOutQuad;

        private RectTransform rectTransform;
        private Tween scaleTween;

        public UnityEvent startGameEvents;

        public bool autoShutDown = false;

        public Image relativeBackground;

        /// <summary>
        /// In milliseconds
        /// </summary>
        public int autoShutDownTime = 5000;

        void Awake()
        {
            rectTransform = GetComponent<RectTransform>();
            if (rectTransform == null)
            {
                Debug.LogError("UI_Scale requires a RectTransform component on the same GameObject.");
            }
        }

        void Start()
        {
            startGameEvents?.Invoke();
        }

        [ContextMenu("Start Scaling")]
        public void StartScaling()
        {
            if (rectTransform == null) return;

            // Kill existing tween if active
            scaleTween?.Kill();

            // Create the scale tween
            scaleTween = rectTransform.DOScale(scaleUp, duration)
                .SetLoops(loops, loopType)
                .SetEase(easeType)
                .OnComplete(() =>
                {
                    //Debug.Log($"Animation is completed");
                });
        }

        [ContextMenu("Stop Scaling")]
        public void StopScaling()
        {
            // Stop the tween and reset scale
            scaleTween?.Kill();
            //rectTransform.localScale = scaleDown;
            // Create the scale tween
            scaleTween = rectTransform.DOScale(scaleDown, duration)
                .SetLoops(loops, loopType)
                .SetEase(easeType)
                .OnComplete(() =>
                {
                    //Debug.Log($"Animation is completed");
                });
        }

        private void OnDestroy()
        {
            // Ensure tweens are cleaned up
            scaleTween?.Kill();
        }



        public async void Execute()
        {
            StartScaling();
            if (relativeBackground != null) relativeBackground.enabled = true;


            if (autoShutDown)
            {
                await Task.Delay(autoShutDownTime);
                Undo();
            }
        }

        public void Undo()
        {
            StopScaling();
            if (relativeBackground != null) relativeBackground.enabled = false;

        }
    }

}