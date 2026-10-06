using UnityEngine;
using UnityEngine.Events;

[RequireComponent(typeof(RectTransform))]
public class LeanTweenRectTransform : MonoBehaviour
{
    [Header("RectTransform Target")]
    [SerializeField] private RectTransform targetRect;

    [Header("Start Transform")]
    [SerializeField] private Vector3 startPosition = Vector3.zero;
    [SerializeField] private Vector2 startSize = new Vector2(100, 100);

    [Header("End Transform")]
    [SerializeField] private Vector3 endPosition = new Vector3(0, 0, 0);
    [SerializeField] private Vector2 endSize = new Vector2(200, 200);

    [Header("Tween Settings")]
    [SerializeField] private float duration = 1f;
    [SerializeField] private float delay = 0f;
    [SerializeField] private LeanTweenType easeType = LeanTweenType.easeInOutSine;
    [SerializeField] private bool playAutomatic = true;
    [SerializeField] private bool loop = false;
    [SerializeField] private bool pingPong = false;

    [Header("Events")]
    public UnityEvent onStart;
    public UnityEvent onComplete;

    private LTDescr moveTween;
    private LTDescr sizeTween;

    private void Reset()
    {
        targetRect = GetComponent<RectTransform>();
    }

    private void Start()
    {
        if (playAutomatic)
            Play();
    }

    /// <summary>
    /// Plays the configured tween animation.
    /// </summary>
    public void Play()
    {
        if (targetRect == null)
            targetRect = GetComponent<RectTransform>();

        // Reset to start state
        targetRect.anchoredPosition3D = startPosition;
        targetRect.sizeDelta = startSize;

        // Fire OnStart event
        onStart?.Invoke();

        // Capture initial position (used to prevent offset drift)
        Vector3 fixedStartPos = startPosition;

        // Move tween
        moveTween = LeanTween.moveLocal(targetRect.gameObject, endPosition, duration)
            .setDelay(delay)
            .setEase(easeType)
            .setOnUpdate((Vector3 val) =>
            {
                // Keep position consistent even when size changes
                targetRect.anchoredPosition3D = val;
            })
            .setOnComplete(() =>
            {
                // ✅ Ensure exact final state
                targetRect.anchoredPosition3D = endPosition;
                targetRect.sizeDelta = endSize;

                // Loop if enabled
                if (loop)
                {
                    Play();
                    return;
                }

                // Fire OnComplete event
                onComplete?.Invoke();
            });

        // Size tween — manually preserve position to prevent drift
        sizeTween = LeanTween.value(targetRect.gameObject, startSize, endSize, duration)
            .setDelay(delay)
            .setEase(easeType)
            .setOnUpdate((Vector2 newSize) =>
            {
                Vector3 currentPos = targetRect.anchoredPosition3D;
                targetRect.sizeDelta = newSize;
                targetRect.anchoredPosition3D = currentPos; // ✅ keep position stable
            });

        // Optional PingPong
        if (pingPong)
        {
            moveTween.setLoopPingPong();
            sizeTween.setLoopPingPong();
        }
    }

    /// <summary>
    /// Plays the animation in reverse (from end → start).
    /// </summary>
    public void PlayReverse()
    {
        (startPosition, endPosition) = (endPosition, startPosition);
        (startSize, endSize) = (endSize, startSize);

        Play();

        // Swap back after playing
        (startPosition, endPosition) = (endPosition, startPosition);
        (startSize, endSize) = (endSize, startSize);
    }
}
