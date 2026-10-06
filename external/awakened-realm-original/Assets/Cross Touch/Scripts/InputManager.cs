using System;
using System.Collections;
using Unity.VisualScripting;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.InputSystem;

namespace CraftSome.CrossTouch
{
    public class InputManager : MonoBehaviour
    {
        #region Variables

        private CrossTouchInput _input;
        public static InputManager Instance { get; private set; }

        [SerializeField] private bool _debugMode = true;

        #endregion

        #region Unity

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }

            Instance = this;
            DontDestroyOnLoad(gameObject);
            _input = new CrossTouchInput();
        }

        private void OnEnable()
        {
            // add the dedicated swipe manager
            if (GetComponent<SwipeManager>() == null)
            {
                var swipeManager = gameObject.AddComponent<SwipeManager>();
                swipeManager.EnableSwipe();

                EnableDedicatedFamily(swipeManager);


            }
            else
            {
                var swipeManager = gameObject.AddComponent<SwipeManager>();
                swipeManager.EnableSwipe();

                EnableDedicatedFamily(swipeManager);
            }

            _input.Touch.Enable();
            _input.MultiTouch.Enable();
            EnableMovementVectorInputs();
            EnablePlayerInput();
            BindInputCallbacks();
            UnityEngine.InputSystem.EnhancedTouch.EnhancedTouchSupport.Enable();
        }

        private void OnDisable()
        {
            if (GetComponent<SwipeManager>() != null)
            {
                var swipeManager = gameObject.GetComponent<SwipeManager>();
                swipeManager.DisableSwipe();

                DisableDedicatedFamily(swipeManager);
            }

            UnbindInputCallbacks();
            _input.Touch.Disable();
            _input.MultiTouch.Disable();
            DisableMovementVectorInputs();
            DisablePlayerInput();
            UnityEngine.InputSystem.EnhancedTouch.EnhancedTouchSupport.Disable();
        }

        private void OnDestroy()
        {
            _input?.Dispose();

            // 🔧 Clear all UnityEvents to prevent leaks between scenes
            OnTap.RemoveAllListeners();
            OnDoubleTap.RemoveAllListeners();
            OnTripleTap.RemoveAllListeners();

            OnHoldStart.RemoveAllListeners();
            OnHoldProgress.RemoveAllListeners();
            OnHoldComplete.RemoveAllListeners();
            OnHoldEnd.RemoveAllListeners();

            OnSwipeStart.RemoveAllListeners();
            OnSwipeProgress.RemoveAllListeners();
            OnSwipeEnd.RemoveAllListeners();
            OnSwipe.RemoveAllListeners();
            OnSwipeDirection.RemoveAllListeners();

            OnDragStart.RemoveAllListeners();
            OnDragProgress.RemoveAllListeners();
            OnDragDirection.RemoveAllListeners();
            OnDragRay.RemoveAllListeners();
            OnDragEnd.RemoveAllListeners();

            OnLookDelta.RemoveAllListeners();
            OnMoveVector.RemoveAllListeners();

            OnPinchStart.RemoveAllListeners();
            OnPinchProgress.RemoveAllListeners();
            OnPinchSpeed.RemoveAllListeners();
            OnPinchEnd.RemoveAllListeners();
            OnTwistProgress.RemoveAllListeners();

            OnXBOX_A_Pressed.RemoveAllListeners();
            OnXBOX_A_Hold.RemoveAllListeners();
            OnXBOX_A_Released.RemoveAllListeners();

            OnXBOX_B_Pressed.RemoveAllListeners();
            OnXBOX_B_Hold.RemoveAllListeners();
            OnXBOX_B_Released.RemoveAllListeners();

            OnXBOX_X_Pressed.RemoveAllListeners();
            OnXBOX_X_Hold.RemoveAllListeners();
            OnXBOX_X_Released.RemoveAllListeners();

            OnXBOX_Y_Pressed.RemoveAllListeners();
            OnXBOX_Y_Hold.RemoveAllListeners();
            OnXBOX_Y_Released.RemoveAllListeners();

            OnXBOX_LB_Pressed.RemoveAllListeners();
            OnXBOX_LB_Hold.RemoveAllListeners();
            OnXBOX_LB_Released.RemoveAllListeners();

            OnXBOX_RB_Pressed.RemoveAllListeners();
            OnXBOX_RB_Hold.RemoveAllListeners();
            OnXBOX_RB_Released.RemoveAllListeners();

            OnXBOX_RT_Pressed.RemoveAllListeners();
            OnXBOX_RT_Released.RemoveAllListeners();
            OnXBOX_RT_Hold.RemoveAllListeners();

            OnXBOX_LT_Pressed.RemoveAllListeners();
            OnXBOX_LT_Released.RemoveAllListeners();
            OnXBOX_LT_Hold.RemoveAllListeners();

            if (_debugMode)
                Debug.Log("[CrossTouch] 🧹 All event listeners cleared on InputManager destroy.");
        }


        private void Update()
        {
            CalculateBtnsUpdate();

#if UNITY_EDITOR || UNITY_STANDALONE
            CheckMouseScrollZoom();
#endif
        }

        #endregion

        #region Bindings

        private void BindInputCallbacks()
        {
            // Tap & Hold will use these
            _input.Touch.PrimaryContact.started += OnPrimaryContactStarted;
            _input.Touch.PrimaryContact.performed += OnPrimaryContactPerformed;
            _input.Touch.PrimaryContact.canceled += OnPrimaryContactCanceled;

            _input.Touch.PrimaryPosition.performed += OnPrimaryPositionPerformed;

            _input.MultiTouch.PrimaryFingerTouch.performed += OnPrimaryFingerTouch;
            _input.MultiTouch.SecondaryFingerTouch.performed += OnSecondaryFingerTouch;
        }

        private void UnbindInputCallbacks()
        {
            _input.Touch.PrimaryContact.started -= OnPrimaryContactStarted;
            _input.Touch.PrimaryContact.performed -= OnPrimaryContactPerformed;
            _input.Touch.PrimaryContact.canceled -= OnPrimaryContactCanceled;

            _input.Touch.PrimaryPosition.performed -= OnPrimaryPositionPerformed;

            _input.MultiTouch.PrimaryFingerTouch.performed -= OnPrimaryFingerTouch;
            _input.MultiTouch.SecondaryFingerTouch.performed -= OnSecondaryFingerTouch;
        }

        #endregion

        #region Tap Family Logic

        private void OnPointerDown()
        {
            _pressStartTime = Time.time;
            _pressStartPos = _currentPointerPosition;

            _isPointerDown = true;
            _dragStartPos = _currentPointerPosition;
            _isDragging = false;

            // 🧭 Swipe tracking start
            _swipeStartTime = Time.time;
            _swipeStartPos = _currentPointerPosition;

            if (_debugMode)
                Debug.Log($"[CrossTouch] Pointer Down at {_pressStartPos}");
        }

        private void OnPointerUp()
        {
            _isPointerDown = false;
            ResetDrag();

            float pressDuration = Time.time - _pressStartTime;
            float movement = Vector2.Distance(_pressStartPos, _currentPointerPosition);

            // ✅ Tap detection
            if (pressDuration <= _tapMaxTime && movement <= _tapMovementThreshold)
                HandleTap(_currentPointerPosition);

#if UNITY_EDITOR || UNITY_STANDALONE

            // 🧭 Swipe detection
            float swipeDuration = Time.time - _swipeStartTime;
            Vector2 swipeVector = _currentPointerPosition - _swipeStartPos;
            float swipeDistance = swipeVector.magnitude;

            if (swipeDuration <= _maxSwipeTime && swipeDistance >= _minSwipeDistance)
            {
                Vector2 direction = _useNormalizedDirection ? swipeVector.normalized : swipeVector;
                OnSwipe?.Invoke(direction);

                SwipeDirection swipeDir = GetSwipeDirection(direction);
                OnSwipeDirection?.Invoke(swipeDir);

                if (_debugMode)
                    Debug.Log(
                        $"[CrossTouch] Swipe detected: {swipeDir} | Distance={swipeDistance:F1}px | Duration={swipeDuration:F2}s");
            }

            // 🟢 End of swipe lifecycle
            if (_isSwiping)
            {
                OnSwipeEnd?.Invoke(_currentPointerPosition);
                _isSwiping = false;
                _swipeStarted = false;

                if (_debugMode)
                    Debug.Log($"[CrossTouch] 🔴 Swipe ended at {_currentPointerPosition}");
            }
#endif

            if (_debugMode)
                Debug.Log($"[CrossTouch] Pointer Up at {_currentPointerPosition}");
        }


        private Coroutine _tapRoutine;

        private void HandleTap(Vector2 position)
        {
            float timeSinceLastTap = Time.time - _lastTapTime;
            _lastTapTime = Time.time;
            _tapCount++;

            if (_debugMode)
                Debug.Log($"[CrossTouch] Tap #{_tapCount} | Δt={timeSinceLastTap:F2}s");

            if (_tapRoutine != null)
                StopCoroutine(_tapRoutine);

            _tapRoutine = StartCoroutine(WaitForNextTap(position));
        }

        private System.Collections.IEnumerator WaitForNextTap(Vector2 position)
        {
            float waitTime = (_tapCount == 2) ? _doubleTapInterval : _tripleTapInterval;
            yield return new WaitForSeconds(waitTime);

            if (_tapCount == 1)
                OnTap?.Invoke(position);
            else if (_tapCount == 2)
                OnDoubleTap?.Invoke(position);
            else if (_tapCount >= 3)
                OnTripleTap?.Invoke(position);

            if (_debugMode)
                Debug.Log($"[CrossTouch] ✅ Fired tap event type: {_tapCount}");

            _tapCount = 0;
            _tapRoutine = null;
        }

        private void ConfirmSingleTap()
        {
            if (_tapCount == 1)
            {
                OnTap?.Invoke(_currentPointerPosition);

                if (_debugMode)
                    Debug.Log($"[CrossTouch] ✅ Single Tap fired at {_currentPointerPosition}");
            }

            _tapCount = 0;
        }

        #endregion

        #region Input Callbacks

        private Vector2 _currentPointerPosition;

        private void OnPrimaryContactStarted(UnityEngine.InputSystem.InputAction.CallbackContext ctx)
        {
            // optional: could mark a “ready to press” state here
        }

        private void OnPrimaryContactPerformed(UnityEngine.InputSystem.InputAction.CallbackContext ctx)
        {
            Debug.Log("[CrossTouch] OnPrimaryContactPerformed fired!");
            OnPointerDown();
            StartHold();
        }


        private void OnPrimaryContactCanceled(UnityEngine.InputSystem.InputAction.CallbackContext ctx)
        {
            Debug.Log("[CrossTouch] OnPrimaryContactCanceled fired!");
            OnPointerUp();
            StopHold();
        }

        private void OnPrimaryPositionPerformed(UnityEngine.InputSystem.InputAction.CallbackContext ctx)
        {
            _currentPointerPosition = ctx.ReadValue<Vector2>();

            HandleDrag();

#if UNITY_EDITOR || UNITY_STANDALONE
            // 🧭 Swipe tracking (real-time)
            if (_pressStartPos != Vector2.zero)
            {
                Vector2 delta = _currentPointerPosition - _swipeStartPos;
                float distance = delta.magnitude;

                // Start swipe once user moves enough distance
                if (!_swipeStarted && distance > _minSwipeDistance)
                {
                    _swipeStarted = true;
                    _isSwiping = true;

                    OnSwipeStart?.Invoke(_currentPointerPosition);
                    if (_debugMode)
                        Debug.Log($"[CrossTouch] 🟡 Swipe started at {_currentPointerPosition}");
                }

                // Continuous swipe updates
                if (_isSwiping)
                {
                    OnSwipeProgress?.Invoke(delta.normalized);
                }
            }

#endif
        }

        #endregion

        #region Tap Family

        #region Tap Detection Data

        private float _pressStartTime;
        private Vector2 _pressStartPos;
        private float _lastTapTime;
        private int _tapCount;

        [Header("🔧 Tap Settings")]
        [SerializeField]
        private float _tapMaxTime = 0.25f; // Max time for one tap

        [SerializeField] private float _doubleTapInterval = 0.35f; // Allowed gap between 1st and 2nd tap
        [SerializeField] private float _tripleTapInterval = 0.45f; // Allowed gap between 2nd and 3rd tap
        [SerializeField] private float _tapMovementThreshold = 15f; // Movement allowed

        #endregion

        public UnityEvent<Vector2> OnTap;
        public UnityEvent<Vector2> OnDoubleTap;
        public UnityEvent<Vector2> OnTripleTap;

        #endregion

        #region Hold Family

        [Header("🔧 Hold Settings")]

        #region Hold Data

        [SerializeField]
        private float _holdThreshold = 0.6f; // Duration to qualify as a "hold"

        [SerializeField] private float _holdProgressInterval = 0.05f; // Interval for continuous progress updates
        [SerializeField] private float _holdMovementTolerance = 25f; // Allowed finger drift during hold

        private bool _isHolding;
        private float _holdStartTime;
        private Vector2 _holdStartPos;
        private Coroutine _holdRoutine;

        #endregion

        #region Hold Events

        [Tooltip("Fires once when the player starts holding (press begins).")]
        public UnityEvent<Vector2> OnHoldStart;

        [Tooltip("Continuously updates while holding. Sends a 0–1 normalized progress value.")]
        public UnityEvent<float> OnHoldProgress;

        [Tooltip("Fires once when hold duration reaches the threshold (hold complete).")]
        public UnityEvent<Vector2> OnHoldComplete;

        [Tooltip(
            "Fires when the player releases finger/mouse, even if hold was incomplete. Also when the hold reaches the time limit, this event automatically invokes as well")]
        public UnityEvent<Vector2> OnHoldEnd; // Fires when user releases


        #region Hold Logic

        private void StartHold()
        {
            if (_isHolding) return;

            _isHolding = true;
            _holdStartTime = Time.time;
            _holdStartPos = _currentPointerPosition;

            OnHoldStart?.Invoke(_holdStartPos);
            if (_debugMode)
                Debug.Log($"[CrossTouch] ⏱ Hold started at {_holdStartPos}");

            _holdRoutine = StartCoroutine(HoldProgressRoutine());
        }

        private void StopHold(bool canceledManually = false)
        {
            if (!_isHolding) return;

            _isHolding = false;

            if (_holdRoutine != null)
                StopCoroutine(_holdRoutine);

            OnHoldEnd?.Invoke(_currentPointerPosition);
            if (_debugMode)
                Debug.Log(
                    $"[CrossTouch] 🖐 Hold ended at {_currentPointerPosition} {(canceledManually ? "(Canceled)" : "")}");
        }

        private IEnumerator HoldProgressRoutine()
        {
            while (_isHolding)
            {
                float elapsed = Time.time - _holdStartTime;
                float normalized = Mathf.Clamp01(elapsed / _holdThreshold);

                // Fire continuous progress updates
                OnHoldProgress?.Invoke(normalized);

                // If finger moved too far, cancel
                float movement = Vector2.Distance(_holdStartPos, _currentPointerPosition);
                if (movement > _holdMovementTolerance)
                {
                    if (_debugMode)
                        Debug.Log($"[CrossTouch] Hold canceled (moved too far: {movement:F1}px)");
                    StopHold(true);
                    yield break;
                }

                // Check if hold completed
                if (elapsed >= _holdThreshold)
                {
                    OnHoldComplete?.Invoke(_currentPointerPosition);
                    if (_debugMode)
                        Debug.Log($"[CrossTouch] ✅ Hold completed after {elapsed:F2}s");
                    StopHold();
                    yield break;
                }

                yield return new WaitForSeconds(_holdProgressInterval);
            }
        }

        #endregion

        #endregion

        #endregion

        #region Swipe Family

        private bool _isSwiping;
        private bool _swipeStarted;

        [Header("🔧 Swipe Settings")]
        [SerializeField, Tooltip("Minimum distance (in pixels) required to register a swipe.")]
        private float _minSwipeDistance = 50f;

        [SerializeField, Tooltip("Maximum time (in seconds) allowed to complete a swipe.")]
        private float _maxSwipeTime = 0.5f;

        [SerializeField] private float _swipeCoolDownTime = .5f;

        [SerializeField, Tooltip("Normalize direction vector for consistent directional strength.")]
        private bool _useNormalizedDirection = true;

        public float MinSwipeDistance => _minSwipeDistance;
        public float MaxSwipeTime => _maxSwipeTime;
        public bool UseNormalizedDirection => _useNormalizedDirection;
        public float SwipeCoolDownTime => _swipeCoolDownTime;


        [Tooltip(
            "Fires once when the player begins swiping — triggered as soon as movement passes the minimum distance threshold.")]
        public UnityEvent<Vector2> OnSwipeStart;

        [Tooltip(
            "Fires continuously while the swipe is in motion, providing the current direction vector (normalized if enabled).")]
        public UnityEvent<Vector2> OnSwipeProgress;

        [Tooltip(
            "Fires once when the swipe ends — usually when the player lifts their finger or the swipe naturally stops.")]
        public UnityEvent<Vector2> OnSwipeEnd;

        [Tooltip("Fires once when a valid swipe gesture is completed. Sends the final direction vector of the swipe.")]
        public UnityEvent<Vector2> OnSwipe;

        [Tooltip(
            "Fires together with OnSwipe, providing the interpreted SwipeDirection (Up, Down, Left, Right, etc.) of the gesture.")]
        public UnityEvent<SwipeDirection> OnSwipeDirection;


        // internal tracking
        private Vector2 _swipeStartPos;
        private float _swipeStartTime;

        #region Swipe Logic

        private SwipeDirection GetSwipeDirection(Vector2 dir)
        {
            if (dir == Vector2.zero)
                return SwipeDirection.None;

            // Normalize the direction vector
            dir.Normalize();

            // Determine horizontal or vertical direction
            if (Mathf.Abs(dir.x) > Mathf.Abs(dir.y))
            {
                // Horizontal swipe (Left or Right)
                return dir.x > 0 ? SwipeDirection.Right : SwipeDirection.Left;
            }
            else
            {
                // Vertical swipe (Up or Down)
                return dir.y > 0 ? SwipeDirection.Up : SwipeDirection.Down;
            }
        }


        #endregion

        #endregion

        #region Drag Family

        [Header("🔧 Drag Settings")]
        [SerializeField]
        private float _dragThreshold = 10f;

        [SerializeField] private float _dragSmoothing = 0.15f;
        [SerializeField] private Camera _raycastCamera;


        [Tooltip("Fires continuously while dragging, sending delta movement in pixels.")]
        public UnityEvent<Vector2> OnDragProgress;

        [Tooltip("Fires continuously with normalized direction (useful for character or camera movement).")]
        public UnityEvent<Vector2> OnDragDirection;

        [Tooltip(
            "Fires when a drag officially begins (after movement passes the threshold). Provides both screen position and world-space ray for gameplay use.")]
        public DragEvent OnDragStart;

        [Tooltip(
            "Fires every frame while dragging, but only when a collider in the selected LayerMask is hit. Provides both screen position and world-space ray.")]
        public DragEvent OnDragRay;

        [Tooltip(
            "Fires once when the drag ends (finger/mouse released). Provides the final screen position and world-space ray.")]
        public DragEvent OnDragEnd;

        // Internal tracking
        private bool _isDragging;
        private Vector2 _dragStartPos;
        private Vector2 _lastDragPos;
        private bool _isPointerDown;

        [SerializeField,
         Tooltip("Only fire OnDragRay when colliders in these layers are hit. Set to 'Everything' for all.")]
        private LayerMask _dragRaycastMask = ~0; // Everything by default


        #region Drag Logic

        private void HandleDrag()
        {
            if (!_isPointerDown) return;

            float distance = Vector2.Distance(_dragStartPos, _currentPointerPosition);
            Ray ray = GetCurrentRay();

            // Start drag when threshold passed
            if (!_isDragging && distance > _dragThreshold)
            {
                _isDragging = true;
                _lastDragPos = _currentPointerPosition;

                OnDragStart?.Invoke(_currentPointerPosition, ray);
                if (_debugMode)
                    Debug.Log($"[CrossTouch] 🟢 Drag started at {_currentPointerPosition}");

                FireRayEvent(ray); // fire initial ray
            }

            // Update drag progress
            if (_isDragging)
            {
                Vector2 delta = (_currentPointerPosition - _lastDragPos) * (1f - _dragSmoothing);
                Vector2 dir = delta.normalized;

                OnDragProgress?.Invoke(delta);
                OnDragDirection?.Invoke(dir);

                FireRayEvent(ray); // continuous ray firing

                if (_debugMode)
                    Debug.Log($"[CrossTouch] ⏩ Drag delta={delta:F2} | dir={dir:F2}");

                _lastDragPos = _currentPointerPosition;
            }
        }


        private void FireRayEvent(Ray ray)
        {
            if (Physics.Raycast(ray, out RaycastHit hit, Mathf.Infinity, _dragRaycastMask))
            {
                OnDragRay?.Invoke(_currentPointerPosition, ray);

                if (_debugMode)
                    Debug.Log(
                        $"[CrossTouch] 🎯 Drag Ray hit: {hit.collider.name} | Layer: {LayerMask.LayerToName(hit.collider.gameObject.layer)}");
            }
        }


        private void ResetDrag()
        {
            if (_isDragging)
            {
                Ray ray = GetCurrentRay();
                OnDragEnd?.Invoke(_currentPointerPosition, ray);

                if (_debugMode)
                    Debug.Log($"[CrossTouch] 🔴 Drag ended at {_currentPointerPosition}");
            }

            _isDragging = false;
        }

        private Ray GetCurrentRay()
        {
            Camera cam = _raycastCamera != null ? _raycastCamera : Camera.main;
            return cam != null ? cam.ScreenPointToRay(_currentPointerPosition) : default;
        }

        #endregion

        #endregion

        #region Zoom Family

        #region Input Callbacks

        private void OnPrimaryFingerTouch(UnityEngine.InputSystem.InputAction.CallbackContext ctx)
        {
            _finger1Pos = ctx.ReadValue<Vector2>();

            if (_debugMode)
                Debug.Log($"[CrossTouch] 👆 Finger1: {_finger1Pos}");

            CheckPinch();
        }

        private void OnSecondaryFingerTouch(UnityEngine.InputSystem.InputAction.CallbackContext ctx)
        {
            _finger2Pos = ctx.ReadValue<Vector2>();

            if (_debugMode)
                Debug.Log($"[CrossTouch] ✌️ Finger2: {_finger2Pos}");

            CheckPinch();
        }

        #endregion

        [Header("🔧 Zoom Settings")]
        [Tooltip("Fires when a pinch (zoom) gesture starts (two fingers detected).")]
        public UnityEvent<float> OnPinchStart;

        [Tooltip("Fires continuously as the pinch (zoom) gesture changes. " +
                 "Scale < 1 means zooming in, scale > 1 means zooming out.")]
        public UnityEvent<float> OnPinchProgress;

        [Tooltip("Fires continuously with pinch zoom velocity (positive = zoom out, negative = zoom in).")]
        public UnityEvent<float> OnPinchSpeed;


        [Tooltip("Fires when the pinch (zoom) gesture ends.")]
        public UnityEvent OnPinchEnd;

        [Tooltip("Fires continuously while the user rotates two fingers. " +
                 "Positive values indicate clockwise rotation, negative indicate counterclockwise, measured in degrees.")]
        public UnityEvent<float> OnTwistProgress;


        private bool _isPinching;
        private float _initialPinchDistance;
        private float _currentPinchDistance;
        private float _pinchScale;
        private float _previousPinchDistance;

        private Vector2 _finger1Pos;
        private Vector2 _finger2Pos;
        private float _previousTwistAngle;

        [SerializeField, Range(0.001f, 0.02f)]
        [Tooltip(
            "Controls how responsive the pinch zoom feels. Lower = slower, Higher = faster. Recommended range: 0.003 – 0.008.")]
        private float _pinchSensitivity = 0.005f;

        [SerializeField, Range(0.1f, 3f)]
        [Tooltip(
            "Controls how responsive twist rotation feels. Lower = slower, Higher = faster. Recommended range: 0.8–1.5.")]
        private float _twistSensitivity = 1f;

        #region Zoom Logic

#if UNITY_EDITOR || UNITY_STANDALONE
        private void CheckMouseScrollZoom()
        {
            float scrollValue = UnityEngine.InputSystem.Mouse.current.scroll.ReadValue().y;

            if (Mathf.Abs(scrollValue) > 0.01f)
            {
                // Convert scroll to pinch-scale change
                float zoomDelta = 1f + (scrollValue * 0.0015f); // tweak multiplier for sensitivity

                OnPinchProgress?.Invoke(zoomDelta);

                if (_debugMode)
                {
                    string direction = zoomDelta < 1f ? "Zoom In" : "Zoom Out";
                    Debug.Log($"[CrossTouch] 🖱 Mouse Scroll → {direction} ({zoomDelta:F3})");
                }
            }
        }
#endif


        private void CheckPinch()
        {
            // ✅ Only proceed if both fingers are active
            if (_finger1Pos == Vector2.zero || _finger2Pos == Vector2.zero)
            {
                if (_isPinching)
                {
                    _isPinching = false;
                    OnPinchEnd?.Invoke();

                    if (_debugMode)
                        Debug.Log("[CrossTouch] 🔴 Pinch End");
                }

                return;
            }

            // 🔹 Calculate distance between the two fingers
            _currentPinchDistance = Vector2.Distance(_finger1Pos, _finger2Pos);

            // 🔹 Calculate zoom delta based on distance change per frame
            float pinchDelta = _currentPinchDistance - _previousPinchDistance;
            float zoomSpeed = pinchDelta * _pinchSensitivity;
            float scaleChange = 1f + zoomSpeed;
            _previousPinchDistance = _currentPinchDistance;

            // 🔹 Get current twist angle
            Vector2 delta = _finger2Pos - _finger1Pos;
            float currentTwistAngle = Mathf.Atan2(delta.y, delta.x) * Mathf.Rad2Deg;

            // 🔹 Detect pinch start
            if (!_isPinching)
            {
                _isPinching = true;
                _initialPinchDistance = _currentPinchDistance;
                _previousTwistAngle = currentTwistAngle;

                OnPinchStart?.Invoke(_initialPinchDistance);

                if (_debugMode)
                    Debug.Log($"[CrossTouch] 🟢 Pinch Start (Initial Distance={_initialPinchDistance:F2})");
                return;
            }

            // 🔹 Continuous pinch zoom feedback
            OnPinchProgress?.Invoke(scaleChange);

            if (_debugMode)
            {
                string zoomDir = scaleChange < 1f ? "Zoom In" : "Zoom Out";
                Debug.Log($"[CrossTouch] 📏 Pinch {zoomDir} | Δ={zoomSpeed:F4}");
            }

            // 🔹 Twist detection with adjustable sensitivity
            float twistDelta = Mathf.DeltaAngle(_previousTwistAngle, currentTwistAngle);
            _previousTwistAngle = currentTwistAngle;

            if (Mathf.Abs(twistDelta) > 0.5f) // filter small jitters
            {
                float adjustedTwist = twistDelta * _twistSensitivity;
                OnTwistProgress?.Invoke(adjustedTwist);

                if (_debugMode)
                    Debug.Log($"[CrossTouch] 🌀 Twist Δ={adjustedTwist:F2}° (raw={twistDelta:F2}°)");
            }
        }

        #endregion

        #endregion

        #region Movement Vector Family

        [Header("🔧 Movement Vector Settings")]
        [SerializeField, Range(0.1f, 10f)]
        private float _lookSensitivity = 1.2f;

        [SerializeField, Range(0.1f, 10f)] private float _moveSensitivity = 1.0f;

        // 🎮 Public events
        [Tooltip("Continuous camera rotation or directional delta from mouse/touch/controller stick.")]
        public UnityEvent<Vector2> OnLookDelta;

        [Tooltip("Continuous movement input from left stick, keyboard, or equivalent touch drag.")]
        public UnityEvent<Vector2> OnMoveVector;

        private void EnableMovementVectorInputs()
        {
            _input.MovementVector.Enable();

            _input.MovementVector.Look.performed += OnLookPerformed;
            _input.MovementVector.Look.canceled += OnLookCanceled;

            _input.MovementVector.Move.performed += OnMovePerformed;
            _input.MovementVector.Move.canceled += OnMoveCanceled;
        }

        private void DisableMovementVectorInputs()
        {
            _input.MovementVector.Disable();

            _input.MovementVector.Look.performed -= OnLookPerformed;
            _input.MovementVector.Look.canceled -= OnLookCanceled;

            _input.MovementVector.Move.performed -= OnMovePerformed;
            _input.MovementVector.Move.canceled -= OnMoveCanceled;
        }

        private void OnLookPerformed(InputAction.CallbackContext ctx)
        {
            Vector2 delta = ctx.ReadValue<Vector2>() * _lookSensitivity;
            OnLookDelta?.Invoke(delta);

            if (_debugMode)
                Debug.Log($"[CrossTouch] 🎯 Look delta: {delta}");
        }

        private void OnMovePerformed(InputAction.CallbackContext ctx)
        {
            Vector2 vector = ctx.ReadValue<Vector2>() * _moveSensitivity;
            OnMoveVector?.Invoke(vector);

            if (_debugMode)
                Debug.Log($"[CrossTouch] 🕹 Move vector: {vector}");
        }

        private void OnLookCanceled(InputAction.CallbackContext ctx)
        {
            OnLookDelta?.Invoke(Vector2.zero);
        }

        private void OnMoveCanceled(InputAction.CallbackContext ctx)
        {
            OnMoveVector?.Invoke(Vector2.zero);
        }

        #endregion

        #region Player Family

        [Header("🔧 Player Settings")]
        [SerializeField]
        private float _xboxBtnsMaxHoldDuration = .5f;

        [SerializeField]
        [Tooltip("Threshold for considering trigger press")]
        private float _triggerPressThreshold = 0.1f;

        // Events for Trigger Continuous Value (Hold Events)
        public UnityEvent<float> OnXBOX_RT_Hold;
        public UnityEvent<float> OnXBOX_LT_Hold;

        // Events for Trigger Pressed/Released (Button-like behavior)
        public UnityEvent OnXBOX_RT_Pressed;
        public UnityEvent OnXBOX_RT_Released;
        public UnityEvent OnXBOX_LT_Pressed;
        public UnityEvent OnXBOX_LT_Released;

        // Events for Button Pressed/Hold/Released
        public UnityEvent OnXBOX_A_Pressed;
        public UnityEvent OnXBOX_A_Hold;
        public UnityEvent OnXBOX_A_Released;

        public UnityEvent OnXBOX_B_Pressed;
        public UnityEvent OnXBOX_B_Hold;
        public UnityEvent OnXBOX_B_Released;

        public UnityEvent OnXBOX_X_Pressed;
        public UnityEvent OnXBOX_X_Hold;
        public UnityEvent OnXBOX_X_Released;

        public UnityEvent OnXBOX_Y_Pressed;
        public UnityEvent OnXBOX_Y_Hold;
        public UnityEvent OnXBOX_Y_Released;

        public UnityEvent OnXBOX_LB_Pressed;
        public UnityEvent OnXBOX_LB_Hold;
        public UnityEvent OnXBOX_LB_Released;

        public UnityEvent OnXBOX_RB_Pressed;
        public UnityEvent OnXBOX_RB_Hold;
        public UnityEvent OnXBOX_RB_Released;

        // Private flags for button states
        private bool _xboxAPressed = false;
        private bool _xboxBPressed = false;
        private bool _xboxXPressed = false;
        private bool _xboxYPressed = false;
        private bool _xboxLBPressed = false;
        private bool _xboxRBPressed = false;

        private bool _xboxRTPressed = false;
        private bool _xboxLTPressed = false;

        // Trigger state tracking for axis values
        private float _xboxRTValue = 0f;
        private float _xboxLTValue = 0f;

        private void EnablePlayerInput()
        {
            _input.Player.Enable();

            // Xbox A Button (Standard Button Events)
            _input.Player.XBOX_A.started += ctx =>
            {
                _xboxAPressed = true;
                OnXBOX_A_Pressed?.Invoke();
                Invoke(nameof(DisableABtn), _xboxBtnsMaxHoldDuration);
            };
            _input.Player.XBOX_A.canceled += ctx =>
            {
                if (!_xboxAPressed) return;
                _xboxAPressed = false;
                OnXBOX_A_Released?.Invoke();
            };

            // Xbox B Button (Standard Button Events)
            _input.Player.XBOX_B.started += ctx =>
            {
                _xboxBPressed = true;
                OnXBOX_B_Pressed?.Invoke();
                Invoke(nameof(DisableBBtn), _xboxBtnsMaxHoldDuration);
            };
            _input.Player.XBOX_B.canceled += ctx =>
            {
                if (!_xboxBPressed) return;
                _xboxBPressed = false;
                OnXBOX_B_Released?.Invoke();
            };

            // Xbox X Button (Standard Button Events)
            _input.Player.XBOX_X.started += ctx =>
            {
                _xboxXPressed = true;
                OnXBOX_X_Pressed?.Invoke();
                Invoke(nameof(DisableXBtn), _xboxBtnsMaxHoldDuration);
            };
            _input.Player.XBOX_X.canceled += ctx =>
            {
                if (!_xboxXPressed) return;
                _xboxXPressed = false;
                OnXBOX_X_Released?.Invoke();
            };

            // Xbox Y Button (Standard Button Events)
            _input.Player.XBOX_Y.started += ctx =>
            {
                _xboxYPressed = true;
                OnXBOX_Y_Pressed?.Invoke();
                Invoke(nameof(DisableYBtn), _xboxBtnsMaxHoldDuration);
            };
            _input.Player.XBOX_Y.canceled += ctx =>
            {
                if (!_xboxYPressed) return;
                _xboxYPressed = false;
                OnXBOX_Y_Released?.Invoke();
            };

            // Xbox LB Button (Standard Button Events)
            _input.Player.XBOX_LB.started += ctx =>
            {
                _xboxLBPressed = true;
                OnXBOX_LB_Pressed?.Invoke();
                Invoke(nameof(DisableLBBtn), _xboxBtnsMaxHoldDuration);
            };
            _input.Player.XBOX_LB.canceled += ctx =>
            {
                if (!_xboxLBPressed) return;
                _xboxLBPressed = false;
                OnXBOX_LB_Released?.Invoke();
            };

            // Xbox RB Button (Standard Button Events)
            _input.Player.XBOX_RB.started += ctx =>
            {
                _xboxRBPressed = true;
                OnXBOX_RB_Pressed?.Invoke();
                Invoke(nameof(DisableRBBtn), _xboxBtnsMaxHoldDuration);
            };
            _input.Player.XBOX_RB.canceled += ctx =>
            {
                if (!_xboxRBPressed) return;
                _xboxRBPressed = false;
                OnXBOX_RB_Released?.Invoke();
            };


            _input.Player.XBOX_RT.started += ctx => { OnXBOX_RT_Pressed?.Invoke(); };

            // Xbox RT (Trigger Axis) - Continuous Hold and Pressed/Released
            _input.Player.XBOX_RT.performed += ctx =>
            {
                _xboxRTValue = ctx.ReadValue<float>();
                OnXBOX_RT_Hold?.Invoke(_xboxRTValue);

                if (!_xboxRTPressed && _xboxRTValue > _triggerPressThreshold)
                {
                    _xboxRTPressed = true;
                    OnXBOX_RT_Pressed?.Invoke(); // Trigger pressed event at the start
                }
            };

            _input.Player.XBOX_RT.canceled += ctx => { OnXBOX_RT_Released?.Invoke(); };


            _input.Player.XBOX_LT.started += ctx => { OnXBOX_LT_Pressed?.Invoke(); };

            // Xbox LT (Trigger Axis) - Continuous Hold and Pressed/Released
            _input.Player.XBOX_LT.performed += ctx =>
            {
                _xboxLTValue = ctx.ReadValue<float>();
                OnXBOX_LT_Hold?.Invoke(_xboxLTValue);

                if (!_xboxLTPressed && _xboxLTValue > _triggerPressThreshold)
                {
                    _xboxLTPressed = true;
                    OnXBOX_LT_Pressed?.Invoke(); // Trigger pressed event at the start
                }

                if (_xboxLTPressed && _xboxLTValue <= _triggerPressThreshold)
                {
                    _xboxLTPressed = false;
                    OnXBOX_LT_Released?.Invoke(); // Trigger released event at the end
                }
            };

            _input.Player.XBOX_LT.canceled += ctx => { OnXBOX_LT_Released?.Invoke(); };
        }

        private void DisablePlayerInput()
        {
            _input.Player.Disable();
        }

        // Disable button after max hold duration
        private void DisableABtn()
        {
            if (!_xboxAPressed) return;
            _xboxAPressed = false;
            OnXBOX_A_Released?.Invoke();
        }

        private void DisableBBtn()
        {
            if (!_xboxBPressed) return;
            _xboxBPressed = false;
            OnXBOX_B_Released?.Invoke();
        }

        private void DisableXBtn()
        {
            if (!_xboxXPressed) return;
            _xboxXPressed = false;
            OnXBOX_X_Released?.Invoke();
        }

        private void DisableYBtn()
        {
            if (!_xboxYPressed) return;
            _xboxYPressed = false;
            OnXBOX_Y_Released?.Invoke();
        }

        private void DisableLBBtn()
        {
            if (!_xboxLBPressed) return;
            _xboxLBPressed = false;
            OnXBOX_LB_Released?.Invoke();
        }

        private void DisableRBBtn()
        {
            if (!_xboxRBPressed) return;
            _xboxRBPressed = false;
            OnXBOX_RB_Released?.Invoke();
        }

        // Continuous hold events in Update method


        // Handle continuous hold events for buttons (for buttons like A, B, X, Y)
        private void CalculateBtnsUpdate()
        {
            if (_xboxAPressed)
                OnXBOX_A_Hold?.Invoke();
            if (_xboxBPressed)
                OnXBOX_B_Hold?.Invoke();
            if (_xboxXPressed)
                OnXBOX_X_Hold?.Invoke();
            if (_xboxYPressed)
                OnXBOX_Y_Hold?.Invoke();
            if (_xboxLBPressed)
                OnXBOX_LB_Hold?.Invoke();
            if (_xboxRBPressed)
                OnXBOX_RB_Hold?.Invoke();
        }

        #endregion



        #region Dedicated Swipe Family For Mobile/Touch

        private void EnableDedicatedFamily(SwipeManager swipeManager)
        {
            swipeManager.OnSwipeStart += HandleSwipeStart;
            swipeManager.OnSwipeProgress += HandleSwipeProgress;
            swipeManager.OnSwipeEnd += HandleSwipeEnd;
            swipeManager.OnSwipeDirection += HandleSwipeDirection;
            swipeManager.OnSwipeDirectionNormalized += HandleSwipeDirectionNormalized;
        }

        private void HandleSwipeDirectionNormalized(Vector2 vector)
        {
            this.OnSwipe?.Invoke(vector);
        }

        private void HandleSwipeDirection(SwipeDirection direction)
        {
            this.OnSwipeDirection?.Invoke(direction);
        }

        private void HandleSwipeEnd(Vector2 vector)
        {
            this.OnSwipeEnd?.Invoke(vector);
        }

        private void HandleSwipeProgress(Vector2 vector)
        {
            this.OnSwipeProgress?.Invoke(vector);
        }

        private void HandleSwipeStart(Vector2 vector)
        {
            this.OnSwipeStart?.Invoke(vector);
        }

        private void DisableDedicatedFamily(SwipeManager swipeManager)
        {
            swipeManager.OnSwipeStart -= HandleSwipeStart;
            swipeManager.OnSwipeProgress -= HandleSwipeProgress;
            swipeManager.OnSwipeEnd -= HandleSwipeEnd;
            swipeManager.OnSwipeDirection -= HandleSwipeDirection;
            swipeManager.OnSwipeDirectionNormalized -= HandleSwipeDirectionNormalized;
        }






        #endregion



    }
}