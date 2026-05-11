"""
gesture.py - Hand Gesture Detection
Detects: Open Hand = OPEN, Closed Fist = CLOSE
"""

import cv2 
import mediapipe as mp
import time

# Setup MediaPipe
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# Finger tip landmarks (thumb, index, middle, ring, pinky)
TIP_IDS = [4, 8, 12, 16, 20]

def count_fingers(landmarks):
    """Count how many fingers are raised."""
    fingers = []

    # Thumb: check if tip is to the left of the joint
    if landmarks[4].x < landmarks[3].x:
        fingers.append(1)
    else:
        fingers.append(0)

    # Other 4 fingers: check if tip is above the middle joint
    for tip in TIP_IDS[1:]:
        if landmarks[tip].y < landmarks[tip - 2].y:
            fingers.append(1)
        else:
            fingers.append(0)

    return sum(fingers)


def run_gesture_detection(on_command, get_running):
    """
    Main gesture detection loop.
    - on_command(cmd): called with "OPEN" or "CLOSE"
    - get_running(): returns True while the mode is active
    """
    cap = cv2.VideoCapture(0)
    hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)

    hold_start = None
    last_gesture = None
    HOLD_TIME = 1.5  # seconds to hold gesture before confirming

    while get_running():
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        gesture = None

        if result.multi_hand_landmarks:
            hand = result.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

            count = count_fingers(hand.landmark)

            if count >= 4:
                gesture = "OPEN"
            elif count <= 1:
                gesture = "CLOSE"

        # Hold timer logic
        if gesture and gesture == last_gesture:
            elapsed = time.time() - hold_start
            progress = min(elapsed / HOLD_TIME, 1.0)

            # Draw progress bar
            bar_width = int(640 * progress)
            cv2.rectangle(frame, (0, 460), (bar_width, 480), (0, 255, 0), -1)

            if elapsed >= HOLD_TIME:
                on_command(gesture)
                hold_start = time.time()  # reset so it doesn't spam
        else:
            last_gesture = gesture
            hold_start = time.time()

        # Show label
        label = gesture if gesture else "No Gesture"
        cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    1.2, (0, 255, 100), 2)

        cv2.imshow("Gesture Detection - Press Q to stop", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
