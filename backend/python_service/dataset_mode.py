"""
DATASET MODE pipeline (offline evaluation).

Datasets mentioned in abstract:
  1. NTHU Driver Drowsiness Dataset (video-based)
  2. MRL Eye Dataset (eye open/closed)
  3. Self-created EAR dataset (CSV logs)

Goal:
  - Reuse SAME algorithms as live mode:
      HOG + SVM (dlib), Dlib 68 landmarks, EAR + temporal features.
  - Compute metrics: accuracy, precision, recall.
  - Optionally store per-video summary in MongoDB.
"""

import argparse
import glob
import html
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import cv2
import dlib
import numpy as np

from ear_utils import compute_frame_ear, compute_frame_ear_features

try:
  from joblib import dump, load  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
  dump = None  # type: ignore[assignment]
  load = None  # type: ignore[assignment]

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DETECTOR = dlib.get_frontal_face_detector()
_PREDICTOR_PATH = "shape_predictor_68_face_landmarks.dat"
_PREDICTOR: Optional[Any] = None

EAR_THRESHOLD = 0.2
MIN_FRAMES_CLOSED = 10  # N consecutive frames threshold (tunable)

MODEL_DEFAULT_PATH = "./models/drowsiness_ear_lr.joblib"
FEATURE_NAMES = ["leftEAR", "rightEAR", "meanEAR", "earDiff", "earRatio"]


def get_predictor(predictor_path: str) -> Any:
  global _PREDICTOR, _PREDICTOR_PATH
  # Make relative paths work no matter where you run the script from.
  resolved_path = predictor_path
  if not os.path.isabs(resolved_path) and not os.path.exists(resolved_path):
    resolved_path = os.path.join(os.path.dirname(__file__), predictor_path)

  if _PREDICTOR is None or resolved_path != _PREDICTOR_PATH:
    if not os.path.exists(resolved_path):
      raise FileNotFoundError(
        f"Missing predictor file: '{predictor_path}'. "
        "Download 'shape_predictor_68_face_landmarks.dat' and place it in backend/python_service/."
      )
    _PREDICTOR = dlib.shape_predictor(resolved_path)
    _PREDICTOR_PATH = resolved_path
  return _PREDICTOR


@dataclass
class VideoResult:
  source: str
  video_name: str
  image_path: str
  avg_ear: float
  min_ear: float
  blink_rate: int
  confidence: float
  face_detected: bool
  label: Literal["AWAKE", "DROWSY"]
  predicted: Literal["AWAKE", "DROWSY"]


def iter_video_frames(path: str):
  cap = cv2.VideoCapture(path)
  try:
    while True:
      ret, frame = cap.read()
      if not ret:
        break
      yield frame
  finally:
    cap.release()


def process_video(path: str, label: Literal["AWAKE", "DROWSY"]) -> VideoResult:
  ears: List[float] = []
  closed_counter = 0
  blink_count = 0

  for frame in iter_video_frames(path):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = DETECTOR(gray, 0)
    if len(faces) == 0:
      continue

    face = faces[0]
    shape = get_predictor(_PREDICTOR_PATH)(gray, face)
    landmarks = np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)])

    ear = compute_frame_ear(landmarks)
    ears.append(ear)

    if ear < EAR_THRESHOLD:
      closed_counter += 1
    else:
      if closed_counter >= MIN_FRAMES_CLOSED:
        blink_count += 1
      closed_counter = 0

  if not ears:
    avg_ear = 0.0
    min_ear = 0.0
  else:
    avg_ear = float(np.mean(ears))
    min_ear = float(np.min(ears))

  # Simple rule-based prediction from EAR statistics
  predicted: Literal["AWAKE", "DROWSY"] = (
    "DROWSY" if avg_ear < EAR_THRESHOLD or min_ear < EAR_THRESHOLD else "AWAKE"
  )

  return VideoResult(
    source="DATASET",
    video_name=os.path.basename(path),
    image_path=os.path.abspath(path),
    avg_ear=avg_ear,
    min_ear=min_ear,
    blink_rate=blink_count,
    confidence=0.0,
    face_detected=True,
    label=label,
    predicted=predicted,
  )


def _extract_features_from_bgr(
  image_bgr: np.ndarray, *, predictor_path: str
) -> Tuple[np.ndarray, Dict[str, float], bool]:
  """Return (feature_vector, feature_dict, face_detected) for a single image."""
  gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
  faces = DETECTOR(gray, 0)
  if len(faces) == 0:
    return np.zeros((len(FEATURE_NAMES),), dtype=np.float32), {}, False

  face = max(faces, key=lambda rect: rect.width() * rect.height())
  predictor = get_predictor(predictor_path)
  shape = predictor(gray, face)
  landmarks = np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)])

  feats = compute_frame_ear_features(landmarks)
  vec = np.array([feats[n] for n in FEATURE_NAMES], dtype=np.float32)
  return vec, feats, True


def _predict_label_and_confidence(model: Any, x_vec: np.ndarray) -> Tuple[str, float]:
  """
  model can be:
    - sklearn Pipeline
    - {"model": pipeline, ...} bundle
  """
  pipeline = model["model"] if isinstance(model, dict) and "model" in model else model
  x2 = x_vec.reshape(1, -1)

  if hasattr(pipeline, "predict_proba"):
    proba = pipeline.predict_proba(x2)[0]
    classes = list(getattr(pipeline, "classes_", [0, 1]))
    idx_pos = classes.index(1) if 1 in classes else 1
    p_drowsy = float(proba[idx_pos])
    predicted = "DROWSY" if p_drowsy >= 0.5 else "AWAKE"
    confidence = p_drowsy if predicted == "DROWSY" else float(1.0 - p_drowsy)
    return predicted, float(max(0.0, min(1.0, confidence)))

  pred = int(pipeline.predict(x2)[0])
  predicted = "DROWSY" if pred == 1 else "AWAKE"
  return predicted, 0.0


def process_image(
  path: str,
  label: Literal["AWAKE", "DROWSY"],
  *,
  predictor_path: str,
  model: Optional[Any],
) -> Optional[VideoResult]:
  """Evaluate a single image (PNG/JPG/...) and return a result row."""
  image = cv2.imread(path)
  if image is None:
    return None

  x_vec, feats, face_detected = _extract_features_from_bgr(
    image, predictor_path=predictor_path
  )

  # Match API behavior: if no face detected, treat as low-confidence AWAKE.
  if not face_detected:
    predicted: Literal["AWAKE", "DROWSY"] = "AWAKE"
    confidence = 0.0
    ear = 0.0
  else:
    ear = float(feats.get("meanEAR", 0.0))
    if model is None:
      left_ear = float(feats.get("leftEAR", 0.0) or 0.0)
      right_ear = float(feats.get("rightEAR", 0.0) or 0.0)
      max_eye_ear = max(left_ear, right_ear)
      # Robust single-image rule: DROWSY only if BOTH eyes are below threshold.
      predicted = "DROWSY" if max_eye_ear < EAR_THRESHOLD else "AWAKE"
      confidence = float(min(1.0, abs(max_eye_ear - EAR_THRESHOLD) / 0.15))
    else:
      predicted, confidence = _predict_label_and_confidence(model, x_vec)

  return VideoResult(
    source="DATASET_IMAGE",
    video_name=os.path.basename(path),
    image_path=os.path.abspath(path),
    avg_ear=float(ear),
    min_ear=float(ear),
    blink_rate=0,
    confidence=float(confidence),
    face_detected=bool(face_detected),
    label=label,
    predicted=predicted,
  )


def _normalize_label_dir_name(name: str) -> str:
  s = name.strip().lower().replace("_", " ").replace("-", " ")
  while "  " in s:
    s = s.replace("  ", " ")
  return s


def _resolve_dataset_label_dirs(root_dir: str) -> Dict[Literal["AWAKE", "DROWSY"], str]:
  """
  Resolve which subfolders correspond to AWAKE vs DROWSY.

  Supports folder names like:
    - Drowsy
    - Non Drowsy / Non-Drowsy / No Drowsey / Awake / Normal
  """
  label_dirs: Dict[Literal["AWAKE", "DROWSY"], str] = {}
  try:
    children = [
      d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))
    ]
  except FileNotFoundError:
    return label_dirs

  for child in children:
    norm = _normalize_label_dir_name(child)

    # Non-drowsy variants → AWAKE
    if "drowsy" in norm and (norm.startswith("non ") or norm.startswith("no ")):
      label_dirs["AWAKE"] = os.path.join(root_dir, child)
      continue
    if norm in {"awake", "normal", "not drowsy", "non drowsey", "no drowsey", "nondrowsy"}:
      label_dirs["AWAKE"] = os.path.join(root_dir, child)
      continue

    # Drowsy variants → DROWSY
    if norm == "drowsy" or ("drowsy" in norm and "non" not in norm and "no " not in norm):
      label_dirs["DROWSY"] = os.path.join(root_dir, child)
      continue
    if norm in {"sleepy"}:
      label_dirs["DROWSY"] = os.path.join(root_dir, child)
      continue

  return label_dirs


def _collect_image_paths(label_dir: str) -> List[str]:
  image_exts = ["png", "jpg", "jpeg", "bmp", "webp", "tif", "tiff"]
  paths: List[str] = []
  for ext in image_exts:
    paths.extend(glob.glob(os.path.join(label_dir, f"*.{ext}")))
    paths.extend(glob.glob(os.path.join(label_dir, f"*.{ext.upper()}")))
  return sorted(paths)


def _take_cap(paths: List[str], max_images: int) -> List[str]:
  if max_images <= 0:
    return paths
  return paths[:max_images]


def _train_or_load_model(
  *,
  dataset_root: str,
  predictor_path: str,
  model_path: str,
  force_train: bool,
  train_if_missing: bool,
  max_per_class: int,
  seed: int,
) -> Tuple[Optional[Any], Dict[str, Any]]:
  """
  Returns (model_or_none, training_summary).
  If model is None, evaluation will fall back to simple EAR-threshold logic.
  """
  summary: Dict[str, Any] = {"modelPath": model_path, "usedModel": False, "trainedNow": False}

  model_file_exists = os.path.exists(model_path)
  if not force_train and model_file_exists:
    if load is None:
      print("[WARN] joblib not available; cannot load model. Falling back to threshold logic.")
      return None, summary
    try:
      model = load(model_path)
      summary["usedModel"] = True
      return model, summary
    except Exception as e:
      print(f"[WARN] Failed to load model '{model_path}': {e}. Will retrain.")

  if not train_if_missing and not model_file_exists and not force_train:
    print("[INFO] Model missing and training disabled. Falling back to threshold logic.")
    return None, summary

  if dump is None:
    print("[WARN] joblib not available; cannot train/save model. Falling back to threshold logic.")
    return None, summary

  label_dirs = _resolve_dataset_label_dirs(dataset_root)
  if "AWAKE" not in label_dirs or "DROWSY" not in label_dirs:
    print("[DATASET MODE] Could not find both label folders under:", os.path.abspath(dataset_root))
    print("Expected: dataset/Drowsy and dataset/Non Drowsy (images).")
    return None, summary

  awake_paths = _take_cap(_collect_image_paths(label_dirs["AWAKE"]), max_per_class)
  drowsy_paths = _take_cap(_collect_image_paths(label_dirs["DROWSY"]), max_per_class)

  X: List[np.ndarray] = []
  y: List[int] = []
  skipped_no_face = 0

  def _add_one(img_path: str, label_int: int):
    nonlocal skipped_no_face
    img = cv2.imread(img_path)
    if img is None:
      return
    x_vec, _, face = _extract_features_from_bgr(img, predictor_path=predictor_path)
    if not face:
      skipped_no_face += 1
      return
    X.append(x_vec)
    y.append(label_int)

  for p in awake_paths:
    _add_one(p, 0)
  for p in drowsy_paths:
    _add_one(p, 1)

  if len(set(y)) < 2 or len(y) < 10:
    print("[WARN] Not enough usable images with detected faces to train. Falling back to threshold logic.")
    summary.update({"trainSamples": len(y), "skippedNoFace": skipped_no_face})
    return None, summary

  X_arr = np.stack(X, axis=0)
  y_arr = np.array(y, dtype=np.int64)

  pipeline = Pipeline(
    steps=[
      ("scaler", StandardScaler()),
      ("clf", LogisticRegression(solver="liblinear", random_state=seed)),
    ]
  )

  X_train, X_test, y_train, y_test = train_test_split(
    X_arr, y_arr, test_size=0.2, random_state=seed, stratify=y_arr
  )
  pipeline.fit(X_train, y_train)
  y_pred = pipeline.predict(X_test)
  cm = confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist()

  bundle = {
    "model": pipeline,
    "featureNames": FEATURE_NAMES,
    "trainedAt": datetime.utcnow().isoformat() + "Z",
    "datasetRoot": os.path.abspath(dataset_root),
    "predictorPath": predictor_path,
    "holdout": {"confusionMatrix": cm, "testSize": int(len(y_test))},
  }

  os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
  dump(bundle, model_path)

  summary.update(
    {
      "usedModel": True,
      "trainedNow": True,
      "trainSamples": int(len(y_arr)),
      "trainSamplesByClass": {"AWAKE": int(np.sum(y_arr == 0)), "DROWSY": int(np.sum(y_arr == 1))},
      "skippedNoFace": int(skipped_no_face),
      "holdout": bundle["holdout"],
    }
  )
  return bundle, summary


def evaluate_dataset(
  root_dir: str,
  *,
  predictor_path: str,
  model: Optional[Any],
  max_per_class: int,
) -> List[VideoResult]:
  """
  dataset/
   ├─ Drowsy/
   │   ├─ img1.png
   └─ Non Drowsy/
       ├─ img2.png
  """
  results: List[VideoResult] = []

  label_dirs = _resolve_dataset_label_dirs(root_dir)
  if "AWAKE" not in label_dirs or "DROWSY" not in label_dirs:
    print("[DATASET MODE] Could not find both label folders under:", os.path.abspath(root_dir))
    print("Expected: dataset/Drowsy and dataset/Non Drowsy (images).")
    return results

  for label in ["AWAKE", "DROWSY"]:
    label_dir = label_dirs[label]  # type: ignore[index]
    all_paths = _collect_image_paths(label_dir)
    paths = _take_cap(all_paths, max_per_class)
    print(f"[DATASET MODE] Scanning: {label_dir} (label={label}) images={len(paths)}/{len(all_paths)}")

    for path in paths:
      res = process_image(
        path,
        label,  # type: ignore[arg-type]
        predictor_path=predictor_path,
        model=model,
      )
      if res is not None:
        results.append(res)

  return results


def compute_metrics(results: List[VideoResult]) -> Dict[str, Any]:
  if not results:
    return {}

  tp = sum(1 for r in results if r.label == "DROWSY" and r.predicted == "DROWSY")
  tn = sum(1 for r in results if r.label == "AWAKE" and r.predicted == "AWAKE")
  fp = sum(1 for r in results if r.label == "AWAKE" and r.predicted == "DROWSY")
  fn = sum(1 for r in results if r.label == "DROWSY" and r.predicted == "AWAKE")
  no_face = sum(1 for r in results if not r.face_detected)

  accuracy = (tp + tn) / max(1, (tp + tn + fp + fn))
  precision = tp / max(1, (tp + fp))
  recall = tp / max(1, (tp + fn))

  print("\n=== DATASET MODE METRICS ===")
  print(f"Accuracy : {accuracy * 100:.2f}%")
  print(f"Precision: {precision * 100:.2f}%")
  print(f"Recall   : {recall * 100:.2f}%")
  print(f"No-Face  : {no_face} / {len(results)} images")

  return {
    "tp": int(tp),
    "tn": int(tn),
    "fp": int(fp),
    "fn": int(fn),
    "noFace": int(no_face),
    "accuracy": float(accuracy),
    "precision": float(precision),
    "recall": float(recall),
    "total": int(len(results)),
  }


def store_results_json(results: List[VideoResult], filename: str = "dataset_results.json"):
  """Stores evaluation results to a local JSON file instead of MongoDB."""
  payloads = [
    {
      "source": r.source,
      "videoName": r.video_name,
      "imagePath": r.image_path,
      "avgEAR": r.avg_ear,
      "minEAR": r.min_ear,
      "blinkRate": r.blink_rate,
      "confidence": r.confidence,
      "faceDetected": r.face_detected,
      "label": r.label,
      "predicted": r.predicted,
    }
    for r in results
  ]

  try:
    with open(filename, "w", encoding="utf-8") as f:
      json.dump(payloads, f, indent=2)
    print(f"\n[SUCCESS] Stored {len(payloads)} results in '{filename}'.")
  except Exception as e:
    print(f"\n[ERROR] Failed to save JSON results: {e}")


def _safe_pct(x: float) -> str:
  return f"{x * 100:.2f}%"


def write_html_report(
  *,
  report_path: str,
  dataset_root: str,
  model_summary: Dict[str, Any],
  metrics: Dict[str, Any],
  results: List[VideoResult],
):
  """Create a lightweight offline HTML report (no extra dependencies)."""
  fp_examples = [r for r in results if r.label == "AWAKE" and r.predicted == "DROWSY"][:25]
  fn_examples = [r for r in results if r.label == "DROWSY" and r.predicted == "AWAKE"][:25]

  def _row(r: VideoResult) -> str:
    badge = "badge badge-red" if r.predicted == "DROWSY" else "badge badge-green"
    gt_badge = "badge badge-red" if r.label == "DROWSY" else "badge badge-green"
    return (
      "<tr>"
      f"<td class='mono'>{html.escape(r.video_name)}</td>"
      f"<td><span class='{gt_badge}'>{r.label}</span></td>"
      f"<td><span class='{badge}'>{r.predicted}</span></td>"
      f"<td class='mono'>{r.avg_ear:.3f}</td>"
      f"<td class='mono'>{r.confidence:.3f}</td>"
      f"<td class='mono'>{'YES' if r.face_detected else 'NO'}</td>"
      f"<td class='path'>{html.escape(r.image_path)}</td>"
      "</tr>"
    )

  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  acc = float(metrics.get("accuracy", 0.0) or 0.0)
  prec = float(metrics.get("precision", 0.0) or 0.0)
  rec = float(metrics.get("recall", 0.0) or 0.0)
  total = int(metrics.get("total", 0) or 0)

  used_model = bool(model_summary.get("usedModel"))
  trained_now = bool(model_summary.get("trainedNow"))
  model_path = str(model_summary.get("modelPath", ""))

  model_line = (
    f"{'Loaded' if used_model and not trained_now else 'Trained'} model: "
    f"<span class='mono'>{html.escape(model_path)}</span>"
    if used_model
    else "Model: <span class='mono'>EAR threshold fallback</span>"
  )

  html_out = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dataset Mode Report</title>
  <style>
    :root {{
      --bg: #0b1020;
      --card: rgba(255,255,255,0.06);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.65);
      --line: rgba(255,255,255,0.10);
      --green: #22c55e;
      --red: #ef4444;
      --amber: #f59e0b;
      --blue: #60a5fa;
      --shadow: 0 20px 60px rgba(0,0,0,0.35);
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      background: radial-gradient(1200px 600px at 15% 15%, rgba(96,165,250,0.25), transparent 55%),
                  radial-gradient(1000px 550px at 85% 25%, rgba(239,68,68,0.18), transparent 55%),
                  radial-gradient(900px 600px at 55% 85%, rgba(34,197,94,0.18), transparent 60%),
                  var(--bg);
      color: var(--text);
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 28px 18px 60px; }}
    .title {{ display: flex; justify-content: space-between; gap: 14px; margin-bottom: 18px; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0.2px; }}
    .subtitle {{ margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .pill {{ background: rgba(255,255,255,0.08); border: 1px solid var(--line); padding: 8px 10px; border-radius: 999px; font-size: 12px; color: var(--muted); white-space: nowrap; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 18px 0 14px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 14px; box-shadow: var(--shadow); backdrop-filter: blur(10px); }}
    .k {{ color: var(--muted); font-size: 12px; margin-bottom: 8px; }}
    .v {{ font-size: 22px; font-weight: 700; letter-spacing: 0.2px; }}
    .note {{ margin-top: 6px; font-size: 12px; color: var(--muted); }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    .section {{ margin-top: 14px; }}
    .section h2 {{ margin: 0 0 10px; font-size: 16px; color: rgba(255,255,255,0.88); }}
    .badge {{ display: inline-block; font-size: 12px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--line); background: rgba(255,255,255,0.08); }}
    .badge-green {{ color: var(--green); }}
    .badge-red {{ color: var(--red); }}
    .badge-amber {{ color: var(--amber); }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 14px; border: 1px solid var(--line); background: rgba(255,255,255,0.04); }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid var(--line); vertical-align: top; font-size: 13px; }}
    th {{ color: rgba(255,255,255,0.75); font-weight: 600; background: rgba(255,255,255,0.06); }}
    tr:last-child td {{ border-bottom: none; }}
    td.path {{ max-width: 520px; color: rgba(255,255,255,0.60); word-break: break-all; }}
    .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} .two {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="title">
      <div>
        <h1>Dataset Mode Report</h1>
        <div class="subtitle">
          <div><span class="badge badge-amber">Dataset</span> <span class="mono">{html.escape(os.path.abspath(dataset_root))}</span></div>
          <div>{model_line}</div>
        </div>
      </div>
      <div class="pill">Generated: <span class="mono">{html.escape(now)}</span></div>
    </div>

    <div class="grid">
      <div class="card"><div class="k">Accuracy</div><div class="v" style="color: var(--blue)">{_safe_pct(acc)}</div><div class="note">Total: <span class="mono">{total}</span></div></div>
      <div class="card"><div class="k">Precision (DROWSY)</div><div class="v" style="color: var(--green)">{_safe_pct(prec)}</div><div class="note">Avoids false alarms</div></div>
      <div class="card"><div class="k">Recall (DROWSY)</div><div class="v" style="color: var(--red)">{_safe_pct(rec)}</div><div class="note">Catches drowsiness</div></div>
      <div class="card"><div class="k">No-Face Frames</div><div class="v">{int(metrics.get('noFace', 0) or 0)}</div><div class="note">Low-confidence AWAKE</div></div>
    </div>

    <div class="two section">
      <div class="card">
        <h2>False Positives (AWAKE → DROWSY)</h2>
        <table><thead><tr><th>Image</th><th>EAR</th><th>Conf</th><th>Face</th><th>Path</th></tr></thead><tbody>
          {''.join(f"<tr><td class='mono'>{html.escape(r.video_name)}</td><td class='mono'>{r.avg_ear:.3f}</td><td class='mono'>{r.confidence:.3f}</td><td class='mono'>{'YES' if r.face_detected else 'NO'}</td><td class='path'>{html.escape(r.image_path)}</td></tr>" for r in fp_examples) or "<tr><td colspan='5' style='color: var(--muted)'>None</td></tr>"}
        </tbody></table>
      </div>
      <div class="card">
        <h2>False Negatives (DROWSY → AWAKE)</h2>
        <table><thead><tr><th>Image</th><th>EAR</th><th>Conf</th><th>Face</th><th>Path</th></tr></thead><tbody>
          {''.join(f"<tr><td class='mono'>{html.escape(r.video_name)}</td><td class='mono'>{r.avg_ear:.3f}</td><td class='mono'>{r.confidence:.3f}</td><td class='mono'>{'YES' if r.face_detected else 'NO'}</td><td class='path'>{html.escape(r.image_path)}</td></tr>" for r in fn_examples) or "<tr><td colspan='5' style='color: var(--muted)'>None</td></tr>"}
        </tbody></table>
      </div>
    </div>

    <div class="section card">
      <h2>Preview (first 200 results)</h2>
      <table>
        <thead><tr><th>Image</th><th>Label</th><th>Pred</th><th>EAR</th><th>Conf</th><th>Face</th><th>Path</th></tr></thead>
        <tbody>
          {''.join(_row(r) for r in results[:200])}
        </tbody>
      </table>
      <div class="note">Preview is capped to keep report fast on huge datasets.</div>
    </div>
  </div>
</body>
</html>"""

  Path(report_path).write_text(html_out, encoding="utf-8")
  print(f"[SUCCESS] HTML report saved: {os.path.abspath(report_path)}")


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Dataset-mode evaluation (images).")
  parser.add_argument("--dataset-root", type=str, default="./dataset", help="Dataset folder root")
  parser.add_argument(
    "--predictor",
    type=str,
    default="shape_predictor_68_face_landmarks.dat",
    help="Path to dlib 68-landmark predictor (.dat)",
  )
  parser.add_argument(
    "--model-path",
    type=str,
    default=MODEL_DEFAULT_PATH,
    help="Where to load/save the trained classifier (joblib).",
  )
  parser.add_argument(
    "--max-per-class",
    type=int,
    default=500,
    help="Cap evaluation/training images per class (0 or negative = all).",
  )
  parser.add_argument("--seed", type=int, default=42, help="Random seed for training split.")
  parser.add_argument(
    "--no-train",
    action="store_true",
    help="Do not train if the model file is missing; fall back to EAR threshold.",
  )
  parser.add_argument(
    "--force-train",
    action="store_true",
    help="Always retrain (overwrites model file).",
  )
  parser.add_argument(
    "--out-json",
    type=str,
    default="dataset_results.json",
    help="Output JSON results path.",
  )
  parser.add_argument(
    "--out-report",
    type=str,
    default="dataset_report.html",
    help="Output HTML report path.",
  )
  args = parser.parse_args()

  model, model_summary = _train_or_load_model(
    dataset_root=args.dataset_root,
    predictor_path=args.predictor,
    model_path=args.model_path,
    force_train=bool(args.force_train),
    train_if_missing=not bool(args.no_train),
    max_per_class=int(args.max_per_class),
    seed=int(args.seed),
  )

  if model_summary.get("usedModel"):
    action = "TRAINED" if model_summary.get("trainedNow") else "LOADED"
    print(f"[MODEL] {action} classifier at: {model_summary.get('modelPath')}")
    if model_summary.get("trainedNow") and model_summary.get("holdout"):
      holdout = model_summary["holdout"]
      print(f"[MODEL] Holdout test size: {holdout.get('testSize')}  CM(awake/drowsy): {holdout.get('confusionMatrix')}")
  else:
    print("[MODEL] Using EAR threshold fallback (no classifier).")

  results = evaluate_dataset(
    args.dataset_root,
    predictor_path=args.predictor,
    model=model,
    max_per_class=int(args.max_per_class),
  )
  metrics = compute_metrics(results)
  store_results_json(results, filename=args.out_json)
  write_html_report(
    report_path=args.out_report,
    dataset_root=args.dataset_root,
    model_summary=model_summary,
    metrics=metrics,
    results=results,
  )


