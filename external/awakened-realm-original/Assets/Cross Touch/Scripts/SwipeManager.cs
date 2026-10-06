using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace CraftSome.CrossTouch
{
    public class SwipeManager : MonoBehaviour


    {
        private CrossTouchInput _input;
        private Vector2 _startTouchPos;
        private Vector2 _currentTouchPos;
        private bool _isSwiping = false;

        // Access values from InputManager instead of hardcoding them
        private float MinSwipeDistance => InputManager.Instance.MinSwipeDistance;
        private float MaxSwipeTime => InputManager.Instance.MaxSwipeTime;
        private bool UseNormalizedDirection => InputManager.Instance.UseNormalizedDirection;

        // Swipe events to be invoked
        public event Action<Vector2> OnSwipeStart;
        public event Action<Vector2> OnSwipeProgress;
        public event Action<Vector2> OnSwipeEnd;
        public event Action<SwipeDirection> OnSwipeDirection;
        public event Action<Vector2> OnSwipeDirectionNormalized; // New action for normalized direction


        [SerializeField] private bool _canDoSwipe = true;

        private void Awake()
        {
            // Ensure this is set up as a singleton
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        public static SwipeManager Instance { get; private set; }

        public void EnableSwipe()
        {
            // Bind the swipe actions
            _input = new CrossTouchInput();
            _input.SwipeTouch.Enable();

            _input.SwipeTouch.PrimaryContact.started += OnPrimaryContact;
            _input.SwipeTouch.PrimaryContact.performed += OnPrimaryContact;
            _input.SwipeTouch.PrimaryContact.canceled += OnPrimaryContact;

            _input.SwipeTouch.PrimaryDelta.started += OnPrimaryDelta;
            _input.SwipeTouch.PrimaryDelta.performed += OnPrimaryDelta;
            _input.SwipeTouch.PrimaryDelta.canceled += OnPrimaryDelta;
        }

        public void DisableSwipe()
        {
            // Unbind actions
            _input.SwipeTouch.Disable();

            _input.SwipeTouch.PrimaryContact.started -= OnPrimaryContact;
            _input.SwipeTouch.PrimaryContact.performed -= OnPrimaryContact;
            _input.SwipeTouch.PrimaryContact.canceled -= OnPrimaryContact;

            _input.SwipeTouch.PrimaryDelta.started -= OnPrimaryDelta;
            _input.SwipeTouch.PrimaryDelta.performed -= OnPrimaryDelta;
            _input.SwipeTouch.PrimaryDelta.canceled -= OnPrimaryDelta;
        }

        /// <summary>
        /// This listener will act as the button press (touch press).
        /// </summary>
        private void OnPrimaryContact(InputAction.CallbackContext context)
        {
            if (context.phase == InputActionPhase.Started)
            {
                // We don't get position here; only track that the touch has started
                _isSwiping = true;
                OnSwipeStart?.Invoke(_startTouchPos); // Start the swipe event, we can track position later
            }
            else if (context.phase == InputActionPhase.Canceled)
            {
                // On touch release, stop the swipe tracking
                _isSwiping = false;
                OnSwipeEnd?.Invoke(_currentTouchPos); // Ending the swipe event
            }
        }

        /// <summary>
        /// This listener tracks the swipe delta (movement).
        /// </summary>
        private void OnPrimaryDelta(InputAction.CallbackContext context)
        {
            if (!_isSwiping) return;

            // Get the current touch position
            _currentTouchPos = context.ReadValue<Vector2>();

            // Calculate the swipe delta (movement since touch started)
            Vector2 swipeDelta = _currentTouchPos - _startTouchPos;

            // Handle swipe progress if the swipe distance exceeds the threshold
            if (swipeDelta.magnitude > MinSwipeDistance)
            {
                OnSwipeProgress?.Invoke(swipeDelta);
                DetermineSwipeDirection(swipeDelta); // Handle swipe direction logic
                CalculateNormalizedDirection(swipeDelta); // Handle normalized direction logic
            }
        }


        private void DetermineSwipeDirection(Vector2 swipeDelta)
        {
            if (swipeDelta.magnitude < MinSwipeDistance) return;
            if (_canDoSwipe == false) return;

            // Dead zone handling for very small movements
            if (Mathf.Abs(swipeDelta.x) < 10f && Mathf.Abs(swipeDelta.y) < 10f)
                return;

            // Calculate swipe direction based on delta X and Y
            SwipeDirection swipeDir = SwipeDirection.None;

            if (Mathf.Abs(swipeDelta.x) > Mathf.Abs(swipeDelta.y)) // Horizontal swipe
            {
                swipeDir = swipeDelta.x > 0 ? SwipeDirection.Right : SwipeDirection.Left;
            }
            else // Vertical swipe
            {
                swipeDir = swipeDelta.y > 0 ? SwipeDirection.Up : SwipeDirection.Down;
            }

            // Optional: Detect diagonal swipes
            if (swipeDir == SwipeDirection.None)
            {
                if (swipeDelta.x > 0 && swipeDelta.y > 0)
                    swipeDir = SwipeDirection.UpRight;
                else if (swipeDelta.x < 0 && swipeDelta.y > 0)
                    swipeDir = SwipeDirection.UpLeft;
                else if (swipeDelta.x < 0 && swipeDelta.y < 0)
                    swipeDir = SwipeDirection.DownLeft;
                else if (swipeDelta.x > 0 && swipeDelta.y < 0)
                    swipeDir = SwipeDirection.DownRight;
            }

            // Invoke the swipe direction event
            OnSwipeDirection?.Invoke(swipeDir);
            _canDoSwipe = false;
            Invoke(nameof(ReEnaleSwipe), InputManager.Instance.SwipeCoolDownTime);
        }


        private void ReEnaleSwipe()
        {
            _canDoSwipe = true;
        }

        // Calculate the normalized direction of the swipe
        private void CalculateNormalizedDirection(Vector2 swipeDelta)
        {
            if (swipeDelta.magnitude < MinSwipeDistance) return;

            Vector2 normalizedDirection = swipeDelta.normalized;
            if (UseNormalizedDirection) // Only invoke if normalization is enabled
            {
                OnSwipeDirectionNormalized?.Invoke(normalizedDirection);
            }
        }
    }



}
