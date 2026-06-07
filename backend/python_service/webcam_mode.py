"""
WEBCAM MODE (local demo).

Purpose:
  - Open the laptop webcam.
  - Run the same pipeline as API / dataset mode:
      HOG + SVM face detector (dlib) + 68 landmarks + EAR logic.
  - Show a live preview window with EAR + AWAKE/DROWSY overlay.
  - Send drowsiness events to backend API for alert timeline.

Usage (from backend/python_service):
  python webcam_mode.py --user-email driver@example.com
  python webcam_mode.py --user-email driver@example.com --camera 0
  python webcam_mode.py --user-email driver@example.com --camera 1 --threshold 0.2 --min-closed 10
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from typing import Literal

import cv2
import dlib
import numpy as np

from ear_utils import compute_frame_ear

# HTTP client for sending events to backend
try:
  import requests
  HAS_REQUESTS = True
except ImportError:
  HAS_REQUESTS = False
  print("WARNING: requests library not found. Events will not be sent to backend.")


import threading

def _send_request_thread(url, payload):
  try:
    response = requests.post(url, json=payload, timeout=5)
    if response.status_code == 200:
      print(f"[API] Event sent successfully: {payload['status']}")
    else:
      print(f"[API] Failed to send event: {response.status_code}")
  except Exception as e:
    print(f"[API] Error sending event: {e}")

def send_event_to_backend(user_email: str, ear: float, status: Literal["AWAKE", "DROWSY"], blink_count: int):
  """Send drowsiness detection event to backend API in a background thread."""
  if not HAS_REQUESTS:
    return
  
  url = "http://localhost:8001/api/ai/webcam-log"
  payload = {
    "user_email": user_email,
    "ear_value": float(ear),
    "status": status,
    "blink_rate": blink_count,
    "confidence": 0.8,
    "timestamp": datetime.now().isoformat()
  }
  
  # Run in background to avoid blocking the camera feed
  thread = threading.Thread(target=_send_request_thread, args=(url, payload), daemon=True)
  thread.start()


def _play_beep_thread():
  """Internal thread function to play a short, crisp single alert beep."""
  try:
    import winsound
    # Play a single crisp beep: 2500Hz for 500ms
    winsound.Beep(2500, 500)
  except Exception:
    # Fallback or silent if winsound fails
    pass

def play_alert_sound():
  """Play an alert beep in a background thread."""
  thread = threading.Thread(target=_play_beep_thread, daemon=True)
  thread.start()


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--user-email", type=str, required=True, help="Email of the logged-in user")
  parser.add_argument("--camera", type=int, default=0, help="Webcam index (0, 1, ...)")
  parser.add_argument("--threshold", type=float, default=0.2, help="EAR threshold for DROWSY")
  parser.add_argument(
    "--min-closed",
    type=int,
    default=10,
    help="N consecutive frames below threshold to count as a blink",
  )
  parser.add_argument(
    "--predictor",
    type=str,
    default="shape_predictor_68_face_landmarks.dat",
    help="Path to dlib 68 landmark predictor (.dat)",
  )
  args = parser.parse_args()

  detector = dlib.get_frontal_face_detector()
  predictor = dlib.shape_predictor(args.predictor)

  # Open camera
  cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
  if cap is None or not cap.isOpened():
    cap = cv2.VideoCapture(args.camera)
  
  if not cap.isOpened():
    print(f"ERROR: Could not open webcam index {args.camera}. Try --camera 1")
    return 1

  ear_threshold = float(args.threshold)
  min_frames_closed = int(args.min_closed)
  user_email = args.user_email

  closed_counter = 0
  blink_count = 0
  status: Literal["AWAKE", "DROWSY"] = "AWAKE"
  last_status = status
  last_status_change = time.time()
  last_event_sent = time.time()  # Track when we last sent an event

  # Performance optimization: Resize frame for detection
  # dlib's face detector is much faster on smaller images.
  # We'll target a width of ~350px for detection.
  DETECTION_WIDTH = 350

  # FPS tracking
  fps_history = []
  last_frame_time = time.time()

  print(f"Webcam mode started for user: {user_email}")
  print("Press 'q' to quit.")

  while True:
    frame_start_time = time.time()
    ok, frame = cap.read()
    if not ok or frame is None:
      continue

    # Resize for detection
    h, w = frame.shape[:2]
    scale = DETECTION_WIDTH / float(w)
    detection_h = int(h * scale)
    detection_frame = cv2.resize(frame, (DETECTION_WIDTH, detection_h))
    
    gray_detection = cv2.cvtColor(detection_frame, cv2.COLOR_BGR2GRAY)
    gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Run face detection on the small frame
    faces = detector(gray_detection, 0)

    ear = 0.0
    face_detected = False

    if len(faces) > 0:
      face_detected = True
      # Choose the largest face in detection frame
      face_small = max(faces, key=lambda r: r.width() * r.height())
      
      # Map face coordinates back to full-resolution frame
      # dlib.rectangle: left, top, right, bottom
      face_full = dlib.rectangle(
        int(face_small.left() / scale),
        int(face_small.top() / scale),
        int(face_small.right() / scale),
        int(face_small.bottom() / scale)
      )
      
      # Run landmark detection on the FULL resolution grayscale image
      # because landmarks are fast once the face bounding box is known,
      # and we want the most precise EAR.
      shape = predictor(gray_full, face_full)
      landmarks = np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)])
      ear = compute_frame_ear(landmarks)

      if ear < ear_threshold:
        closed_counter += 1
        status = "DROWSY"
      else:
        # count a "blink" when eye was closed long enough and then opened
        if closed_counter >= min_frames_closed:
          blink_count += 1
        closed_counter = 0
        status = "AWAKE"

    # Send event to backend when status changes OR every 2 seconds
    # This ensures the dashboard always shows current EAR values
    current_time = time.time()
    should_send = (status != last_status) or (current_time - last_event_sent >= 2.0)
    
    if should_send and face_detected:
      send_event_to_backend(user_email, ear, status, blink_count)
      
      # Play sound alert only on NEW drowsiness detection
      if status == "DROWSY" and last_status != "DROWSY":
        print(f"[ALERT] Drowsiness detected!")
        # play_alert_sound() # Beep sound removed as requested
        
      last_event_sent = current_time
      if status != last_status:
        last_status = status

    # Simple on-screen overlay
    color = (0, 255, 0) if status == "AWAKE" else (0, 0, 255)
    cv2.putText(
      frame,
      f"Status: {status}",
      (10, 30),
      cv2.FONT_HERSHEY_SIMPLEX,
      0.9,
      color,
      2,
      cv2.LINE_AA,
    )
    cv2.putText(
      frame,
      f"EAR: {ear:.3f}  BlinkCount: {blink_count}",
      (10, 60),
      cv2.FONT_HERSHEY_SIMPLEX,
      0.7,
      (255, 255, 255),
      2,
      cv2.LINE_AA,
    )
    
    # Calculate FPS
    now = time.time()
    dt = now - last_frame_time
    last_frame_time = now
    if dt > 0:
      fps_history.append(1.0 / dt)
      if len(fps_history) > 30:
        fps_history.pop(0)
    current_fps = sum(fps_history) / len(fps_history) if fps_history else 0.0

    cv2.putText(
      frame,
      f"FPS: {current_fps:.1f}  FaceDetected: {face_detected}",
      (10, 90),
      cv2.FONT_HERSHEY_SIMPLEX,
      0.7,
      (255, 255, 255),
      2,
      cv2.LINE_AA,
    )

    cv2.imshow("AI Drowsiness Detection (Webcam Mode)", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
      break

    # Keep a stable status readout in console (optional, low frequency)
    if now - last_status_change >= 2.0:
      print(f"[LIVE] status={status} ear={ear:.3f} blinks={blink_count} fps={current_fps:.1f}")
      last_status_change = now

  cap.release()
  cv2.destroyAllWindows()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())

