import numpy as np
from scipy.spatial import distance as dist


# Indices for the 68-point landmark model (Dlib)
LEFT_EYE_POINTS = list(range(36, 42))
RIGHT_EYE_POINTS = list(range(42, 48))
MOUTH_POINTS = list(range(60, 68)) # Inner mouth points


def eye_aspect_ratio(eye_points: np.ndarray) -> float:
  """
  Compute Eye Aspect Ratio (EAR) for one eye.

  EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)
  """
  p2_p6 = dist.euclidean(eye_points[1], eye_points[5])
  p3_p5 = dist.euclidean(eye_points[2], eye_points[4])
  p1_p4 = dist.euclidean(eye_points[0], eye_points[3])

  if p1_p4 == 0:
    return 0.0

  ear = (p2_p6 + p3_p5) / (2.0 * p1_p4)
  return float(ear)


def compute_frame_ear(landmarks: np.ndarray) -> float:
  """
  Compute EAR for a frame given all 68 landmarks as (x, y).

  Returns mean EAR over left and right eye.
  """
  left_eye = landmarks[LEFT_EYE_POINTS]
  right_eye = landmarks[RIGHT_EYE_POINTS]

  left_ear = eye_aspect_ratio(left_eye)
  right_ear = eye_aspect_ratio(right_eye)

  return float((left_ear + right_ear) / 2.0)


def compute_frame_ear_features(landmarks: np.ndarray) -> dict:
  """
  Compute a small feature set from 68 landmarks.

  This does NOT change any existing behavior (used only for dataset-mode training).
  """
  left_eye = landmarks[LEFT_EYE_POINTS]
  right_eye = landmarks[RIGHT_EYE_POINTS]

  left_ear = eye_aspect_ratio(left_eye)
  right_ear = eye_aspect_ratio(right_eye)
  mean_ear = float((left_ear + right_ear) / 2.0)
  ear_diff = float(abs(left_ear - right_ear))  # Ratio is helpful when one eye is partially occluded.
  denom = max(1e-9, float(max(left_ear, right_ear)))
  ear_ratio = float(min(left_ear, right_ear) / denom)
  return {
    "leftEAR": float(left_ear),
    "rightEAR": float(right_ear),
    "meanEAR": mean_ear,
    "earDiff": ear_diff,
    "earRatio": ear_ratio,
  }


def compute_frame_mar(landmarks: np.ndarray) -> float:
  """
  Compute Mouth Aspect Ratio (MAR) for inner mouth.
  MAR = (||p2 - p8|| + ||p3 - p7||) / (2 * ||p1 - p5||)
  Points: p1(60), p2(61), p3(62), p5(64), p7(66), p8(67)
  """
  mouth = landmarks[MOUTH_POINTS]
  p2_p8 = dist.euclidean(mouth[1], mouth[7])
  p3_p7 = dist.euclidean(mouth[2], mouth[6])
  p1_p5 = dist.euclidean(mouth[0], mouth[4])

  if p1_p5 == 0:
    return 0.0

  mar = (p2_p8 + p3_p7) / (2.0 * p1_p5)
  return float(mar)
