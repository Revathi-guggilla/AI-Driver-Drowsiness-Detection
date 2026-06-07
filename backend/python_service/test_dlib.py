import cv2
import dlib
import numpy as np
import os
from pathlib import Path

def test_dlib_on_webcam():
    BASE_DIR = Path(__file__).resolve().parent
    PREDICTOR_PATH = str((BASE_DIR / "shape_predictor_68_face_landmarks.dat").resolve())
    
    if not os.path.exists(PREDICTOR_PATH):
        print(f"ERROR: Predictor path {PREDICTOR_PATH} does not exist.")
        return
    
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    
    print("Opening webcam...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return
    
    print("Capturing 5 frames to check for faces...")
    for i in range(5):
        ret, frame = cap.read()
        if not ret:
            print(f"Frame {i}: Failed to capture.")
            continue
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector(gray, 0)
        print(f"Frame {i}: Detected {len(faces)} face(s).")
        
    cap.release()

if __name__ == "__main__":
    test_dlib_on_webcam()
