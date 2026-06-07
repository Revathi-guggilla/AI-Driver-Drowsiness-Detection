"""
Python ML Service (REST) for AI-Based Driver Drowsiness Detection.

Algorithms (as per abstract):
  - HOG + Linear SVM (via dlib.get_frontal_face_detector) for face detection
  - Dlib 68-point facial landmark detector (Ensemble of Regression Trees)
  - Eye Aspect Ratio (EAR) for drowsiness logic
"""

import base64
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import cv2
import dlib
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from ear_utils import compute_frame_ear, compute_frame_ear_features


DETECTOR = dlib.get_frontal_face_detector()

# Path to 68-landmark predictor file (downloaded separately)
BASE_DIR = Path(__file__).resolve().parent
PREDICTOR_PATH = str((BASE_DIR / "shape_predictor_68_face_landmarks.dat").resolve())
PREDICTOR = dlib.shape_predictor(PREDICTOR_PATH)

# Simple global config for EAR-based logic
# You can tune without code changes:
#   set EAR_THRESHOLD=0.20 (default) in your env.
EAR_THRESHOLD = float(os.getenv("EAR_THRESHOLD", "0.20"))

# Dataset UI/config (does not affect LIVE endpoint behavior)
DATASET_ROOT = str((BASE_DIR / "dataset").resolve())
DATASET_MODEL_PATH = str((BASE_DIR / "models" / "drowsiness_ear_lr.joblib").resolve())
DATASET_UI_PATH = str((BASE_DIR / "static" / "dataset_ui.html").resolve())
DATASET_BROWSER_UI_PATH = str((BASE_DIR / "static" / "dataset_browser.html").resolve())
DATASET_TRAIN_MAX_PER_CLASS = 300
DATASET_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}

# Dataset prediction mode:
# - If true: use trained classifier when available
# - If false: always use EAR threshold (more consistent for demos)
# Default is TRUE to preserve prior behavior; you can override with DATASET_USE_MODEL=0.
DATASET_DEFAULT_USE_MODEL = os.getenv("DATASET_USE_MODEL", "1").strip().lower() in {
  "1",
  "true",
  "yes",
  "y",
}

# Lazy model cache for dataset UI
_DATASET_MODEL_LOCK = threading.Lock()
_DATASET_MODEL: Optional[Any] = None
_DATASET_MODEL_SUMMARY: Dict[str, Any] = {}

# Lazy index cache for dataset browser (file listing only)
_DATASET_INDEX_LOCK = threading.Lock()
_DATASET_INDEX: Dict[str, Dict[str, Any]] = {}

try:
  import dataset_mode as ds  # reuses training/prediction utilities
except Exception:
  ds = None  # type: ignore[assignment]

app = FastAPI(
  title="AI Drowsiness Detection Service",
  description=(
    "Lightweight HOG + SVM + Dlib + EAR service for real-time driver drowsiness "
    "detection and dataset evaluation."
  ),
  version="1.0.0",
)

# Allow React dev server (localhost:3000 or localhost:3001) to call dataset endpoints.
app.add_middleware(
  CORSMiddleware,
  allow_origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
  ],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


class FrameRequest(BaseModel):
  """Single-frame request for LIVE MODE.

  image_base64: Base64-encoded RGB/BGR image (JPEG/PNG).
  """

  image_base64: str


class FrameResponse(BaseModel):
  ear: float
  status: Literal["AWAKE", "DROWSY"]
  confidence: float
  face_detected: bool
  # Dataset UI extras (kept optional so LIVE mode stays unchanged)
  used_model: Optional[bool] = None
  model_path: Optional[str] = None


def decode_base64_image(image_base64: str) -> Optional[np.ndarray]:
  try:
    image_bytes = base64.b64decode(image_base64)
    image_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_arr, cv2.IMREAD_COLOR)
    return image
  except Exception:
    return None


def infer_ear_from_frame(image_bgr: np.ndarray) -> FrameResponse:
  gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

  # HOG + Linear SVM face detector (dlib)
  faces = DETECTOR(gray, 1)

  if len(faces) == 0:
    # No face – treat as low confidence
    return FrameResponse(
      ear=0.0,
      status="AWAKE",
      confidence=0.0,
      face_detected=False,
    )

  # For simplicity, take the largest face
  face = max(faces, key=lambda rect: rect.width() * rect.height())
  shape = PREDICTOR(gray, face)
  landmarks = np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)])

  ear = compute_frame_ear(landmarks)
  feats = compute_frame_ear_features(landmarks)
  left_ear = float(feats.get("leftEAR", 0.0) or 0.0)
  right_ear = float(feats.get("rightEAR", 0.0) or 0.0)

  # Robust single-image rule:
  # Treat as DROWSY only if BOTH eyes are below threshold.
  # This avoids false alarms for blinks / partial occlusion (one eye low).
  max_eye_ear = max(left_ear, right_ear)
  status: Literal["AWAKE", "DROWSY"] = "DROWSY" if max_eye_ear < EAR_THRESHOLD else "AWAKE"

  # Simple confidence: scaled by how far EAR is from threshold
  diff = abs(max_eye_ear - EAR_THRESHOLD)
  confidence = float(min(1.0, diff / 0.15))

  return FrameResponse(
    ear=ear,
    status=status,
    confidence=confidence,
    face_detected=True,
  )


def _get_dataset_model() -> tuple[Optional[Any], Dict[str, Any]]:
  """
  Loads model if present; if missing, trains once and caches.
  This is used ONLY by dataset upload UI endpoints.
  """
  global _DATASET_MODEL, _DATASET_MODEL_SUMMARY

  if ds is None:
    return None, {"usedModel": False, "reason": "dataset_mode import failed"}

  with _DATASET_MODEL_LOCK:
    if _DATASET_MODEL is not None:
      return _DATASET_MODEL, _DATASET_MODEL_SUMMARY

    model, summary = ds._train_or_load_model(  # type: ignore[attr-defined]
      dataset_root=DATASET_ROOT,
      predictor_path=PREDICTOR_PATH,
      model_path=DATASET_MODEL_PATH,
      force_train=False,
      train_if_missing=True,
      max_per_class=DATASET_TRAIN_MAX_PER_CLASS,
      seed=42,
    )
    _DATASET_MODEL = model
    _DATASET_MODEL_SUMMARY = summary
    return _DATASET_MODEL, _DATASET_MODEL_SUMMARY


def _decode_upload_to_bgr(file_bytes: bytes) -> np.ndarray:
  arr = np.frombuffer(file_bytes, dtype=np.uint8)
  img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
  if img is None:
    raise HTTPException(status_code=400, detail="Invalid image file (could not decode).")
  return img


def _boolish(x: Optional[bool]) -> Optional[bool]:
  # FastAPI will already coerce query params to bool when annotated as bool,
  # but keep this helper for optional toggles.
  return None if x is None else bool(x)


def _resolve_dataset_dirs() -> Dict[Literal["AWAKE", "DROWSY"], str]:
  """
  Find the two dataset class folders under DATASET_ROOT.

  Expected default structure:
    dataset/
      Drowsy/
      Non Drowsy/
  """
  # Prefer the dataset_mode resolver because it supports more naming variants.
  if ds is not None and hasattr(ds, "_resolve_dataset_label_dirs"):
    try:
      dirs = ds._resolve_dataset_label_dirs(DATASET_ROOT)  # type: ignore[attr-defined]
      out: Dict[Literal["AWAKE", "DROWSY"], str] = {}
      if isinstance(dirs, dict):
        if "AWAKE" in dirs:
          out["AWAKE"] = str(dirs["AWAKE"])
        if "DROWSY" in dirs:
          out["DROWSY"] = str(dirs["DROWSY"])
      if "AWAKE" in out and "DROWSY" in out:
        return out
    except Exception:
      pass

  # Fallback to the repo's default folder names.
  drowsy = Path(DATASET_ROOT) / "Drowsy"
  non_drowsy = Path(DATASET_ROOT) / "Non Drowsy"
  out2: Dict[Literal["AWAKE", "DROWSY"], str] = {}
  if drowsy.exists() and drowsy.is_dir():
    out2["DROWSY"] = str(drowsy.resolve())
  if non_drowsy.exists() and non_drowsy.is_dir():
    out2["AWAKE"] = str(non_drowsy.resolve())
  return out2


def _is_safe_filename(name: str) -> bool:
  # Disallow path traversal and Windows drive tricks.
  if not name or name != os.path.basename(name):
    return False
  if any(sep in name for sep in ("/", "\\", ":", "\0")):
    return False
  return True


def _resolve_image_path(label: Literal["AWAKE", "DROWSY"], name: str) -> Path:
  if not _is_safe_filename(name):
    raise HTTPException(status_code=400, detail="Invalid file name.")

  ext = Path(name).suffix.lower()
  if ext not in DATASET_ALLOWED_EXTS:
    raise HTTPException(status_code=400, detail="Unsupported file type.")

  dirs = _resolve_dataset_dirs()
  if label not in dirs:
    raise HTTPException(status_code=404, detail=f"Dataset label folder not found: {label}")

  base = Path(dirs[label]).resolve()
  p = (base / name).resolve()
  try:
    p.relative_to(base)
  except Exception:
    raise HTTPException(status_code=400, detail="Invalid file path.") from None

  if not p.exists() or not p.is_file():
    raise HTTPException(status_code=404, detail="Image not found.")
  return p


def _list_images_cached(label: Literal["AWAKE", "DROWSY"]) -> list[str]:
  dirs = _resolve_dataset_dirs()
  if label not in dirs:
    return []

  folder = dirs[label]
  try:
    mtime = os.path.getmtime(folder)
  except Exception:
    mtime = 0.0

  key = label
  with _DATASET_INDEX_LOCK:
    cached = _DATASET_INDEX.get(key)
    if cached and float(cached.get("mtime", 0.0)) == float(mtime) and isinstance(
      cached.get("files"), list
    ):
      return list(cached["files"])

    try:
      names = [
        n
        for n in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, n))
        and Path(n).suffix.lower() in DATASET_ALLOWED_EXTS
        and _is_safe_filename(n)
      ]
    except Exception:
      names = []

    names_sorted = sorted(names, key=lambda s: s.lower())
    _DATASET_INDEX[key] = {"mtime": mtime, "files": names_sorted, "dir": folder}
    return list(names_sorted)


@app.get("/api/ai/health")
def health():
  return {"status": "ok", "algorithm": "HOG+SVM + Dlib 68-landmarks + EAR"}


@app.post("/api/ai/launch-webcam")
def launch_webcam(user_email: str = Query(..., description="Email of the logged-in user")):
  """
  Launch webcam_mode.py in a separate process.
  This opens the camera directly using OpenCV.
  """
  try:
    webcam_script = BASE_DIR / "webcam_mode.py"
    print(f"[DEBUG] BASE_DIR: {BASE_DIR}")
    print(f"[DEBUG] webcam_script path: {webcam_script}")
    print(f"[DEBUG] webcam_script exists: {webcam_script.exists()}")
    print(f"[DEBUG] user_email: {user_email}")
    
    if not webcam_script.exists():
      raise HTTPException(status_code=404, detail=f"webcam_mode.py not found at {webcam_script}")
    
    # Launch the webcam mode script in a separate process
    # Pass user email as argument so webcam can log events
    # Set working directory to BASE_DIR so all imports work correctly
    # Using CREATE_NEW_CONSOLE on Windows to open in a new window
    if sys.platform == "win32":
      print(f"[DEBUG] Launching on Windows with cwd={BASE_DIR}")
      subprocess.Popen(
        [sys.executable, "webcam_mode.py", "--user-email", user_email],
        cwd=str(BASE_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE
      )
    else:
      print(f"[DEBUG] Launching on non-Windows with cwd={BASE_DIR}")
      subprocess.Popen(
        [sys.executable, "webcam_mode.py", "--user-email", user_email],
        cwd=str(BASE_DIR)
      )
    
    print("[DEBUG] Webcam process launched successfully")
    return {"status": "launched", "message": "Webcam mode started successfully"}
  except HTTPException:
    raise
  except Exception as e:
    print(f"[ERROR] Failed to launch webcam: {e}")
    raise HTTPException(status_code=500, detail=f"Failed to launch webcam mode: {str(e)}")


class WebcamLogRequest(BaseModel):
  """Request body for webcam drowsiness logs."""
  user_email: str
  ear_value: float
  status: Literal["AWAKE", "DROWSY", "WARNING"]
  blink_rate: Optional[int] = None
  confidence: Optional[float] = None
  timestamp: Optional[str] = None


@app.post("/api/ai/webcam-log")
async def log_webcam_event(payload: WebcamLogRequest):
  """
  Receive drowsiness detection events from webcam_mode.py and forward to Node.js backend.
  This endpoint is unauthenticated since the webcam runs independently.
  """
  try:
    print(f"[WEBCAM LOG] User: {payload.user_email}, Status: {payload.status}, EAR: {payload.ear_value}")
    
    # Forward to Node.js backend
    try:
      import requests
      
      # Node.js backend URL
      node_backend = os.getenv("NODE_BACKEND_URL", "http://localhost:5001")
      endpoint = f"{node_backend}/api/driver/webcam-log"
      
      # Prepare payload for Node.js backend
      node_payload = {
        "user_email": payload.user_email,
        "ear_value": payload.ear_value,
        "status": payload.status,
        "blink_rate": payload.blink_rate,
        "confidence": payload.confidence,
        "timestamp": payload.timestamp
      }
      
      # Send to Node.js backend
      response = requests.post(endpoint, json=node_payload, timeout=5)
      
      if response.status_code in (200, 201):
        print(f"[WEBCAM LOG] Successfully forwarded to Node.js backend")
        return {
          "status": "logged",
          "message": f"Event logged for {payload.user_email}",
          "data": response.json()
        }
      else:
        print(f"[WEBCAM LOG ERROR] Node.js backend returned {response.status_code}: {response.text}")
        raise HTTPException(status_code=500, detail=f"Backend returned {response.status_code}")
        
    except requests.exceptions.RequestException as e:
      print(f"[WEBCAM LOG ERROR] Failed to connect to Node.js backend: {e}")
      raise HTTPException(status_code=503, detail=f"Failed to connect to backend: {str(e)}")
    
  except HTTPException:
    raise
  except Exception as e:
    print(f"[ERROR] Failed to log webcam event: {e}")
    raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}")


@app.post("/api/ai/live/frame", response_model=FrameResponse)
def process_live_frame(payload: FrameRequest):
  """
  LIVE MODE:
  - Input: one video frame from webcam (base64-encoded image).
  - Output: EAR value + drowsiness status for that frame.

  Note:
    Continuous EAR < threshold logic (N consecutive frames → DROWSY alert)
    can be implemented on the frontend or Node.js backend using this EAR stream.
  """
  image = decode_base64_image(payload.image_base64)
  if image is None:
    return FrameResponse(
      ear=0.0,
      status="AWAKE",
      confidence=0.0,
      face_detected=False,
    )

  return infer_ear_from_frame(image)


@app.get("/dataset-ui", response_class=HTMLResponse)
def dataset_ui():
  """Browser UI to upload a single image and get output."""
  if not os.path.exists(DATASET_UI_PATH):
    raise HTTPException(status_code=404, detail="dataset_ui.html not found.")
  return HTMLResponse(Path(DATASET_UI_PATH).read_text(encoding="utf-8"))


@app.get("/dataset-browser", response_class=HTMLResponse)
def dataset_browser_ui():
  """Browser UI to browse dataset images (AWAKE/DROWSY)."""
  if not os.path.exists(DATASET_BROWSER_UI_PATH):
    raise HTTPException(status_code=404, detail="dataset_browser.html not found.")
  return HTMLResponse(Path(DATASET_BROWSER_UI_PATH).read_text(encoding="utf-8"))


@app.get("/api/ai/dataset/model")
def dataset_model_status():
  model, summary = _get_dataset_model()
  return {
    "usedModel": bool(summary.get("usedModel")) if isinstance(summary, dict) else False,
    "trainedNow": bool(summary.get("trainedNow")) if isinstance(summary, dict) else False,
    "modelPath": summary.get("modelPath") if isinstance(summary, dict) else None,
    "datasetRoot": DATASET_ROOT,
    "trainMaxPerClass": DATASET_TRAIN_MAX_PER_CLASS,
    "ready": model is not None,
  }


@app.post("/api/ai/dataset/predict", response_model=FrameResponse)
async def dataset_predict(
  file: UploadFile = File(...),
  use_model: Optional[bool] = Query(
    None, description="If true uses classifier; if false uses EAR threshold"
  ),
):
  """
  DATASET UI:
  - Input: single uploaded image (multipart/form-data).
  - Output: status + confidence.
  """
  file_bytes = await file.read()
  if not file_bytes:
    raise HTTPException(status_code=400, detail="Empty upload.")

  image_bgr = _decode_upload_to_bgr(file_bytes)

  # Decide whether to use the classifier or threshold rule.
  use_model2 = DATASET_DEFAULT_USE_MODEL if _boolish(use_model) is None else bool(use_model)

  # If dataset pipeline is available, we can use trained model; otherwise fall back to EAR threshold.
  model, summary = _get_dataset_model()
  model_path = str(summary.get("modelPath")) if isinstance(summary, dict) else None

  if (not use_model2) or ds is None:
    res = infer_ear_from_frame(image_bgr)
    res.used_model = False
    res.model_path = model_path
    return res

  x_vec, feats, face = ds._extract_features_from_bgr(  # type: ignore[attr-defined]
    image_bgr, predictor_path=PREDICTOR_PATH
  )
  if not face:
    return FrameResponse(
      ear=0.0,
      status="AWAKE",
      confidence=0.0,
      face_detected=False,
      used_model=bool(summary.get("usedModel")) if isinstance(summary, dict) else False,
      model_path=model_path,
    )

  ear = float(feats.get("meanEAR", 0.0))
  if model is None:
    left_ear = float(feats.get("leftEAR", 0.0) or 0.0)
    right_ear = float(feats.get("rightEAR", 0.0) or 0.0)
    max_eye_ear = max(left_ear, right_ear)
    status: Literal["AWAKE", "DROWSY"] = "DROWSY" if max_eye_ear < EAR_THRESHOLD else "AWAKE"
    diff = abs(max_eye_ear - EAR_THRESHOLD)
    confidence = float(min(1.0, diff / 0.15))
    used_model = False
  else:
    predicted, conf = ds._predict_label_and_confidence(model, x_vec)  # type: ignore[attr-defined]
    status = "DROWSY" if predicted == "DROWSY" else "AWAKE"
    confidence = float(conf)
    used_model = True

  return FrameResponse(
    ear=ear,
    status=status,
    confidence=float(max(0.0, min(1.0, confidence))),
    face_detected=True,
    used_model=bool(used_model),
    model_path=model_path,
  )


@app.get("/api/ai/dataset/summary")
def dataset_summary():
  """
  Dataset Browser API:
  - Provides class counts + sample image URLs.
  """
  dirs = _resolve_dataset_dirs()
  awake_files = _list_images_cached("AWAKE") if "AWAKE" in dirs else []
  drowsy_files = _list_images_cached("DROWSY") if "DROWSY" in dirs else []

  def _sample_urls(label: Literal["AWAKE", "DROWSY"], files: list[str], k: int = 12):
    return [
      {
        "name": name,
        "url": f"/api/ai/dataset/image?label={label}&name={name}",
      }
      for name in files[:k]
    ]

  return {
    "datasetRoot": DATASET_ROOT,
    "labelsFound": sorted(list(dirs.keys())),
    "counts": {"AWAKE": len(awake_files), "DROWSY": len(drowsy_files)},
    "samples": {
      "AWAKE": _sample_urls("AWAKE", awake_files),
      "DROWSY": _sample_urls("DROWSY", drowsy_files),
    },
  }


@app.get("/api/ai/dataset/list")
def dataset_list(
  label: Optional[Literal["AWAKE", "DROWSY"]] = Query(None),
  offset: int = Query(0, ge=0),
  limit: int = Query(48, ge=1, le=200),
  q: Optional[str] = Query(None, description="Optional filename substring filter"),
):
  """
  Dataset Browser API:
  - Returns paginated image names for a label (or all if label is None).
  """
  if label:
    # specific label
    files = [{"name": n, "label": label} for n in _list_images_cached(label)]
  else:
    # all labels
    awake = [{"name": n, "label": "AWAKE"} for n in _list_images_cached("AWAKE")]
    drowsy = [{"name": n, "label": "DROWSY"} for n in _list_images_cached("DROWSY")]
    files = awake + drowsy
    # Sort by name to mix them (or by mtime if we had it, but name is stable)
    files.sort(key=lambda x: x["name"].lower())

  total = len(files)

  if q:
    q2 = q.strip().lower()
    if q2:
      files = [f for f in files if q2 in f["name"].lower()]

  filtered_total = len(files)
  page = files[offset : offset + limit]

  items = [
    {
        "name": item["name"],
        "label": item["label"],
        "url": f"/api/ai/dataset/image?label={item['label']}&name={item['name']}"
    }
    for item in page
  ]

  return {
    "label": label or "ALL",
    "offset": int(offset),
    "limit": int(limit),
    "total": int(filtered_total if q else total),
    "items": items,
    "query": q or "",
  }


@app.get("/api/ai/dataset/image")
def dataset_image(
  label: Literal["AWAKE", "DROWSY"] = Query(...),
  name: str = Query(...),
):
  """Serve a single dataset image file by label + filename."""
  p = _resolve_image_path(label, name)
  return FileResponse(str(p))


@app.get("/api/ai/dataset/predict-from-dataset", response_model=FrameResponse)
def dataset_predict_from_dataset(
  label: Literal["AWAKE", "DROWSY"] = Query(...),
  name: str = Query(...),
  use_model: Optional[bool] = Query(
    None, description="If true uses classifier; if false uses EAR threshold"
  ),
):
  """
  Dataset Browser API:
  - Predict on an existing dataset image (no upload needed).
  """
  p = _resolve_image_path(label, name)
  file_bytes = p.read_bytes()
  image_bgr = _decode_upload_to_bgr(file_bytes)

  use_model2 = DATASET_DEFAULT_USE_MODEL if _boolish(use_model) is None else bool(use_model)

  model, summary = _get_dataset_model()
  model_path = str(summary.get("modelPath")) if isinstance(summary, dict) else None

  # If dataset pipeline is unavailable, fall back to threshold logic.
  if (not use_model2) or ds is None:
    res = infer_ear_from_frame(image_bgr)
    res.used_model = False
    res.model_path = model_path
    return res

  x_vec, feats, face = ds._extract_features_from_bgr(  # type: ignore[attr-defined]
    image_bgr, predictor_path=PREDICTOR_PATH
  )
  if not face:
    return FrameResponse(
      ear=0.0,
      status="AWAKE",
      confidence=0.0,
      face_detected=False,
      used_model=bool(summary.get("usedModel")) if isinstance(summary, dict) else False,
      model_path=model_path,
    )

  ear = float(feats.get("meanEAR", 0.0))
  if model is None:
    left_ear = float(feats.get("leftEAR", 0.0) or 0.0)
    right_ear = float(feats.get("rightEAR", 0.0) or 0.0)
    max_eye_ear = max(left_ear, right_ear)
    status2: Literal["AWAKE", "DROWSY"] = "DROWSY" if max_eye_ear < EAR_THRESHOLD else "AWAKE"
    diff = abs(max_eye_ear - EAR_THRESHOLD)
    confidence2 = float(min(1.0, diff / 0.15))
    used_model2 = False
  else:
    predicted, conf = ds._predict_label_and_confidence(model, x_vec)  # type: ignore[attr-defined]
    status2 = "DROWSY" if predicted == "DROWSY" else "AWAKE"
    confidence2 = float(conf)
    used_model2 = True

  return FrameResponse(
    ear=ear,
    status=status2,
    confidence=float(max(0.0, min(1.0, confidence2))),
    face_detected=True,
    used_model=bool(used_model2),
    model_path=model_path,
  )


@app.get("/api/ai/dataset/results")
def dataset_results():
  """
  Dataset Result API:
  - Loads dataset_results.json and returns a list for the EAR graph.
  """
  results_path = BASE_DIR / "dataset_results.json"
  if not results_path.exists():
    return {"items": []}
  
  try:
    import json
    with open(results_path, "r") as f:
      data = json.load(f)
      
    # Map to Chart format {time, ear}
    # We take a sample or limit to avoid overwhelming the graph
    # If the dataset is large, we take every Nth item or just the first 100
    limit = 100
    raw_items = data[:limit] if isinstance(data, list) else []
    
    items = []
    for i, entry in enumerate(raw_items):
      # Use index or parts of filename as 'time' label for now
      label = entry.get("source", f"item{i}")
      if "/" in label or "\\" in label:
        label = os.path.basename(label)
        
      items.append({
        "time": label,
        "ear": entry.get("avgEAR", 0.0)
      })
      
    return {"items": items}
  except Exception as e:
    print(f"[ERROR] Failed to load dataset results: {e}")
    return {"items": [], "error": str(e)}


if __name__ == "__main__":
  import uvicorn

  port = int(os.getenv("PORT", "8001"))
  uvicorn.run(app, host="0.0.0.0", port=port)


