using UnityEngine;
using CraftSome.CrossTouch;

#if UNITY_EDITOR
[ExecuteAlways]
#endif
public class CrossTouchVisualizer : MonoBehaviour
{
    private InputManager _input;
    private Vector2 _lastTouchPos;
    private Vector2 _lastSwipeDir;
    private Vector2 _finger1, _finger2;
    private bool _isDragging, _isHolding, _isSwiping, _isPinching;

    private void OnEnable()
    {
        _input = InputManager.Instance;
        if (_input == null)
        {
            Debug.LogWarning("[CrossTouchVisualizer] InputManager not found in scene.");
            enabled = false;
            return;
        }

        // 👆 TAP & HOLD
        _input.OnTap.AddListener(pos => { _lastTouchPos = pos; StartFlash(); });
        _input.OnHoldStart.AddListener(pos => { _lastTouchPos = pos; _isHolding = true; });
        _input.OnHoldEnd.AddListener(pos => _isHolding = false);

        // 👆 SWIPE
        _input.OnSwipeStart.AddListener(pos => { _lastTouchPos = pos; _isSwiping = true; });
        _input.OnSwipeEnd.AddListener(pos => _isSwiping = false);
        _input.OnSwipeDirection.AddListener(dir => _lastSwipeDir = DirectionToVector(dir));

        // 👆 DRAG
        _input.OnDragStart.AddListener((pos, ray) => { _lastTouchPos = pos; _isDragging = true; });
        _input.OnDragEnd.AddListener((pos, ray) => _isDragging = false);

        // 👆 PINCH
        _input.OnPinchStart.AddListener(dist => _isPinching = true);
        _input.OnPinchEnd.AddListener(() => _isPinching = false);
    }

    private void OnDisable()
    {
        if (_input == null) return;

        _input.OnTap.RemoveAllListeners();
        _input.OnHoldStart.RemoveAllListeners();
        _input.OnHoldEnd.RemoveAllListeners();
        _input.OnSwipeStart.RemoveAllListeners();
        _input.OnSwipeEnd.RemoveAllListeners();
        _input.OnSwipeDirection.RemoveAllListeners();
        _input.OnDragStart.RemoveAllListeners();
        _input.OnDragEnd.RemoveAllListeners();
        _input.OnPinchStart.RemoveAllListeners();
        _input.OnPinchEnd.RemoveAllListeners();
    }

    // 🔹 Simple flashing dot for tap visualization
    private float _flashTimer;
    private void StartFlash() => _flashTimer = 0.3f;

    private void Update()
    {
#if UNITY_EDITOR
        if (_flashTimer > 0) _flashTimer -= Time.deltaTime;
#endif
    }

    private void OnDrawGizmos()
    {
#if UNITY_EDITOR
        if (_input == null) return;

        Vector3 worldPos = ScreenToWorld(_lastTouchPos);

        // 💠 Tap flash
        if (_flashTimer > 0)
        {
            Gizmos.color = Color.yellow;
            Gizmos.DrawSphere(worldPos, 0.2f);
        }

        // 🟢 Hold visualization
        if (_isHolding)
        {
            Gizmos.color = Color.green;
            Gizmos.DrawWireSphere(worldPos, 0.3f + Mathf.PingPong(Time.time * 0.3f, 0.2f));
        }

        // 🔵 Swipe arrow
        if (_isSwiping && _lastSwipeDir != Vector2.zero)
        {
            Gizmos.color = Color.cyan;
            Vector3 end = worldPos + new Vector3(_lastSwipeDir.x, _lastSwipeDir.y, 0f) * 1.5f;
            Gizmos.DrawLine(worldPos, end);
            Gizmos.DrawSphere(end, 0.1f);
        }

        // 🟣 Drag line
        if (_isDragging)
        {
            Gizmos.color = Color.magenta;
            Gizmos.DrawWireCube(worldPos, Vector3.one * 0.3f);
        }

        // 🔻 Pinch indicator
        if (_isPinching)
        {
            Gizmos.color = Color.red;
            Gizmos.DrawWireSphere(worldPos, 0.5f);
        }
#endif
    }

    private Vector3 ScreenToWorld(Vector2 screenPos)
    {
        Camera cam = Camera.main;
        if (cam == null) return Vector3.zero;
        return cam.ScreenToWorldPoint(new Vector3(screenPos.x, screenPos.y, cam.nearClipPlane + 5f));
    }

    private Vector2 DirectionToVector(SwipeDirection dir)
    {
        return dir switch
        {
            SwipeDirection.Up => Vector2.up,
            SwipeDirection.Down => Vector2.down,
            SwipeDirection.Left => Vector2.left,
            SwipeDirection.Right => Vector2.right,
            SwipeDirection.UpLeft => (Vector2.up + Vector2.left).normalized,
            SwipeDirection.UpRight => (Vector2.up + Vector2.right).normalized,
            SwipeDirection.DownLeft => (Vector2.down + Vector2.left).normalized,
            SwipeDirection.DownRight => (Vector2.down + Vector2.right).normalized,
            _ => Vector2.zero
        };
    }
}
