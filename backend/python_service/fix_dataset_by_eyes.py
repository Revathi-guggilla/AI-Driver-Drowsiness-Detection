"""
Fix dataset labels purely by eye state (open/closed).

Folder mapping (default):
  - AWAKE  -> "Non Drowsy"
  - DROWSY -> "Drowsy"

Decision rule (single image):
  - If max(leftEAR, rightEAR) >= EAR_THRESHOLD  -> AWAKE (eyes open)
  - Else                                       -> DROWSY (eyes closed)

This script ONLY moves/copies images between the two dataset folders.
It does not change any other functionality.
"""

from __future__ import annotations

import argparse
import bz2
import json
import os
import shutil
import time
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Tuple

import cv2
import dlib
import numpy as np

from ear_utils import compute_frame_ear_features


Label = Literal["AWAKE", "DROWSY"]

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")
DLIB_PREDICTOR_URL = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"


def _normalize_dir_name(name: str) -> str:
  s = name.strip().lower().replace("_", " ").replace("-", " ")
  while "  " in s:
    s = s.replace("  ", " ")
  return s


def _resolve_dataset_dirs(dataset_root: str) -> Dict[Label, str]:
  """
  Resolve which subfolders correspond to AWAKE vs DROWSY.
  Supports folder names like:
    - Drowsy
    - Non Drowsy / Non-Drowsy / Awake / Normal
  """
  out: Dict[Label, str] = {}
  root = Path(dataset_root)
  if not root.exists():
    return out

  for child in root.iterdir():
    if not child.is_dir():
      continue
    norm = _normalize_dir_name(child.name)

    # Non-drowsy variants → AWAKE
    if "drowsy" in norm and (norm.startswith("non ") or norm.startswith("no ")):
      out["AWAKE"] = str(child)
      continue
    if norm in {"awake", "normal", "not drowsy", "nondrowsy", "non drowsey", "no drowsey"}:
      out["AWAKE"] = str(child)
      continue

    # Drowsy variants → DROWSY
    if norm == "drowsy" or ("drowsy" in norm and "non" not in norm and "no " not in norm):
      out["DROWSY"] = str(child)
      continue
    if norm in {"sleepy"}:
      out["DROWSY"] = str(child)
      continue

  return out


def _iter_images(folder: str) -> Iterable[str]:
  p = Path(folder)
  if not p.exists():
    return []
  # Only top-level (matches your current dataset layout)
  return (str(x) for x in p.iterdir() if x.is_file() and x.suffix.lower() in IMAGE_EXTS)


def _pick_largest_face(rects: List[dlib.rectangle]) -> dlib.rectangle:
  return max(rects, key=lambda r: int(r.width() * r.height()))


def _ensure_predictor(predictor_path: str, *, allow_download: bool) -> str:
  """
  Ensure predictor exists on disk. Optionally downloads dlib's 68-landmarks model.
  Returns resolved predictor path.
  """
  path = Path(predictor_path)
  if not path.is_absolute():
    # Resolve relative to this file (python_service/)
    path = (Path(__file__).parent / path).resolve()

  if path.exists():
    return str(path)

  if not allow_download:
    raise FileNotFoundError(
      f"Missing predictor file: '{path}'.\n"
      f"Fix: re-run with --download-predictor to fetch it from {DLIB_PREDICTOR_URL}\n"
      "Or manually download and place it at backend/python_service/shape_predictor_68_face_landmarks.dat"
    )

  path.parent.mkdir(parents=True, exist_ok=True)
  tmp_bz2 = path.with_suffix(path.suffix + ".bz2")

  print(f"[DOWNLOAD] Fetching predictor from: {DLIB_PREDICTOR_URL}")
  print(f"[DOWNLOAD] Saving to: {tmp_bz2}", flush=True)
  urllib.request.urlretrieve(DLIB_PREDICTOR_URL, tmp_bz2)  # nosec - intended download

  print(f"[DOWNLOAD] Decompressing to: {path}", flush=True)
  with bz2.open(tmp_bz2, "rb") as f_in, open(path, "wb") as f_out:
    shutil.copyfileobj(f_in, f_out)

  try:
    tmp_bz2.unlink(missing_ok=True)
  except Exception:
    pass

  if not path.exists():
    raise RuntimeError("Download finished but predictor file not found on disk.")
  return str(path)


@dataclass
class FixRow:
  file: str
  src_label: Label
  predicted: Label
  moved: bool
  face_detected: bool
  left_ear: float
  right_ear: float
  mean_ear: float


def _extract_ear_features(
  image_bgr: np.ndarray,
  *,
  detector: Any,
  predictor: Any,
) -> Tuple[bool, float, float, float]:
  gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
  rects = detector(gray, 0)
  if len(rects) == 0:
    return False, 0.0, 0.0, 0.0

  rect = _pick_largest_face(list(rects))
  shape = predictor(gray, rect)
  landmarks = np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)], dtype=np.int32)

  feats = compute_frame_ear_features(landmarks)
  left_ear = float(feats.get("leftEAR", 0.0) or 0.0)
  right_ear = float(feats.get("rightEAR", 0.0) or 0.0)
  mean_ear = float(feats.get("meanEAR", 0.0) or 0.0)
  return True, left_ear, right_ear, mean_ear


def _decide_label(left_ear: float, right_ear: float, *, ear_threshold: float) -> Label:
  # Eyes-open if at least one eye is clearly open.
  return "AWAKE" if max(left_ear, right_ear) >= ear_threshold else "DROWSY"


def _unique_dest_path(dest_dir: str, filename: str) -> str:
  base = Path(dest_dir) / filename
  if not base.exists():
    return str(base)

  stem = base.stem
  suf = base.suffix
  i = 1
  while True:
    cand = base.with_name(f"{stem}__moved{i}{suf}")
    if not cand.exists():
      return str(cand)
    i += 1


def _move_or_copy(src: str, dst: str, *, copy: bool) -> None:
  Path(dst).parent.mkdir(parents=True, exist_ok=True)
  if copy:
    shutil.copy2(src, dst)
  else:
    shutil.move(src, dst)


def fix_dataset(
  *,
  dataset_root: str,
  predictor_path: str,
  ear_threshold: float,
  dry_run: bool,
  copy: bool,
  max_images: int,
  no_face_policy: Literal["keep", "awake", "drowsy", "unknown"],
  progress_every: int,
) -> Tuple[List[FixRow], Dict[str, int]]:
  dirs = _resolve_dataset_dirs(dataset_root)
  if "AWAKE" not in dirs or "DROWSY" not in dirs:
    raise FileNotFoundError(
      "Could not find both dataset folders under:\n"
      f"  {os.path.abspath(dataset_root)}\n"
      "Expected folders like: dataset/Drowsy and dataset/Non Drowsy"
    )

  awake_dir = dirs["AWAKE"]
  drowsy_dir = dirs["DROWSY"]
  unknown_dir = str(Path(dataset_root) / "Unknown")

  detector = dlib.get_frontal_face_detector()
  resolved_predictor = _ensure_predictor(predictor_path, allow_download=False)
  predictor = dlib.shape_predictor(resolved_predictor)

  # Collect files first (so moving doesn't change iteration)
  src_files: List[Tuple[str, Label]] = []
  for p in _iter_images(awake_dir):
    src_files.append((p, "AWAKE"))
  for p in _iter_images(drowsy_dir):
    src_files.append((p, "DROWSY"))

  if max_images > 0:
    src_files = src_files[:max_images]

  rows: List[FixRow] = []
  counts = {"scanned": 0, "moved": 0, "kept": 0, "no_face": 0, "errors": 0}
  t0 = time.time()

  for path, src_label in src_files:
    counts["scanned"] += 1
    img = cv2.imread(path)
    if img is None:
      counts["errors"] += 1
      continue

    try:
      face, left_ear, right_ear, mean_ear = _extract_ear_features(
        img, detector=detector, predictor=predictor
      )
    except Exception:
      counts["errors"] += 1
      continue

    if not face:
      counts["no_face"] += 1
      if no_face_policy == "keep":
        rows.append(
          FixRow(
            file=path,
            src_label=src_label,
            predicted=src_label,
            moved=False,
            face_detected=False,
            left_ear=0.0,
            right_ear=0.0,
            mean_ear=0.0,
          )
        )
        counts["kept"] += 1
        continue
      if no_face_policy == "unknown":
        predicted = src_label
        dst_dir = unknown_dir
      elif no_face_policy == "awake":
        predicted = "AWAKE"
        dst_dir = awake_dir
      else:
        predicted = "DROWSY"
        dst_dir = drowsy_dir
    else:
      predicted = _decide_label(left_ear, right_ear, ear_threshold=ear_threshold)
      dst_dir = awake_dir if predicted == "AWAKE" else drowsy_dir

    moved = False
    if predicted != src_label or (not face and no_face_policy in {"awake", "drowsy", "unknown"} and dst_dir != (awake_dir if src_label == "AWAKE" else drowsy_dir)):
      moved = True
      dst = _unique_dest_path(dst_dir, Path(path).name)
      if not dry_run:
        _move_or_copy(path, dst, copy=copy)
      counts["moved"] += 1
    else:
      counts["kept"] += 1

    rows.append(
      FixRow(
        file=path,
        src_label=src_label,
        predicted=predicted,
        moved=moved,
        face_detected=bool(face),
        left_ear=float(left_ear),
        right_ear=float(right_ear),
        mean_ear=float(mean_ear),
      )
    )

    if progress_every > 0 and (counts["scanned"] % progress_every == 0):
      elapsed = max(1e-6, time.time() - t0)
      rate = counts["scanned"] / elapsed
      print(
        f"[PROGRESS] scanned={counts['scanned']} moved={counts['moved']} kept={counts['kept']} "
        f"no_face={counts['no_face']} errors={counts['errors']} ({rate:.2f} img/s)",
        flush=True,
      )

  return rows, counts


def main() -> int:
  parser = argparse.ArgumentParser(
    description="Move dataset images between Non Drowsy (awake) and Drowsy based only on eyes open/closed (EAR)."
  )
  parser.add_argument("--dataset-root", type=str, default="./dataset", help="Dataset root folder")
  parser.add_argument(
    "--predictor",
    type=str,
    default="shape_predictor_68_face_landmarks.dat",
    help="Path to dlib 68-landmark predictor (.dat)",
  )
  parser.add_argument("--ear-threshold", type=float, default=0.2, help="EAR threshold for eyes closed/open")
  parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Do not move/copy files; only report what would change.",
  )
  parser.add_argument(
    "--copy",
    action="store_true",
    help="Copy instead of move (keeps originals).",
  )
  parser.add_argument(
    "--max-images",
    type=int,
    default=0,
    help="Process at most N images (0 = all).",
  )
  parser.add_argument(
    "--no-face-policy",
    type=str,
    default="keep",
    choices=["keep", "awake", "drowsy", "unknown"],
    help="What to do when no face/landmarks found.",
  )
  parser.add_argument(
    "--progress-every",
    type=int,
    default=500,
    help="Print progress every N images (0 disables).",
  )
  parser.add_argument(
    "--out-json",
    type=str,
    default="dataset_fix_results.json",
    help="Where to save per-file results JSON.",
  )
  parser.add_argument(
    "--download-predictor",
    action="store_true",
    help="If predictor is missing, download it automatically (internet required).",
  )
  args = parser.parse_args()

  # Ensure predictor exists (optionally download).
  try:
    predictor_path = _ensure_predictor(args.predictor, allow_download=bool(args.download_predictor))
  except Exception as e:
    print(f"[ERROR] {e}")
    return 2

  # Run fix pass
  try:
    # We pass predictor_path as absolute/resolved but internal fix_dataset currently uses allow_download=False.
    rows, counts = fix_dataset(
      dataset_root=args.dataset_root,
      predictor_path=predictor_path,
      ear_threshold=float(args.ear_threshold),
      dry_run=bool(args.dry_run),
      copy=bool(args.copy),
      max_images=int(args.max_images),
      no_face_policy=args.no_face_policy,  # type: ignore[arg-type]
      progress_every=int(args.progress_every),
    )
  except Exception as e:
    print(f"[ERROR] {e}")
    return 2

  payload = {
    "datasetRoot": str(Path(args.dataset_root).resolve()),
    "predictor": predictor_path,
    "earThreshold": float(args.ear_threshold),
    "dryRun": bool(args.dry_run),
    "copy": bool(args.copy),
    "noFacePolicy": str(args.no_face_policy),
    "counts": counts,
    "rows": [asdict(r) for r in rows],
  }

  try:
    Path(args.out_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
  except Exception as e:
    print(f"[WARN] Failed to write JSON report '{args.out_json}': {e}")

  print("\n=== DATASET FIX SUMMARY ===")
  print(f"Scanned : {counts['scanned']}")
  print(f"Moved   : {counts['moved']}{' (dry-run)' if args.dry_run else ''}")
  print(f"Kept    : {counts['kept']}")
  print(f"No-face : {counts['no_face']}")
  print(f"Errors  : {counts['errors']}")
  print(f"Report  : {os.path.abspath(args.out_json)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())

