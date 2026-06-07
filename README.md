# Driver Drowsiness Detection Using Eye Blink Rate

### 🛠️ Skills & Technologies

* **Programming Languages** ➜ Python, TypeScript, JavaScript
* **Computer Vision** ➜ OpenCV, Dlib
* **Frontend** ➜ React, TypeScript, Chart.js
* **Backend** ➜ Node.js, Express.js, FastAPI
* **Database** ➜ PostgreSQL
* **Libraries** ➜ NumPy, SciPy
* **Tools** ➜ Git, GitHub

---

## 📌 Project Overview

**Driver Drowsiness Detection** is a computer vision-based safety system designed to monitor a driver's eye movements in real time and detect signs of fatigue or drowsiness. The system analyzes the driver's eye blink rate and eye closure duration through a webcam feed and generates an alert when drowsiness is detected, helping to prevent road accidents.

### 🎯 Objective
To improve road safety by identifying driver fatigue at an early stage and providing timely alerts to maintain driver awareness.

---

## ✨ Key Features

* **Real-time Monitoring**: Continuous driver eye tracking using a standard webcam feed.
* **Eye Detection & Tracking**: High-accuracy face and eye tracking using HOG + Linear SVM.
* **Eye Blink Rate (EBR) Calculation**: Analyzes eye blink patterns to differentiate between normal blinks and fatigue.
* **Drowsiness Detection**: Intelligent classification based on Eye Aspect Ratio (EAR) temporal thresholding.
* **Instant Warnings**: Real-time audio and visual alerts generated on the driver dashboard.
* **Dual Dashboard Panels**: Complete user dashboard for drivers and comprehensive logs/charts for admins.
* **Lightweight & High Performance**: Optimized dual-service architecture (FastAPI for CV, Express for APIs).

---

## ⚙️ Working Principle

Drowsiness detection is calculated based on the distance between the eyelids using the 68-point facial landmarks:

$$\text{EAR} = \frac{||P_2 - P_6|| + ||P_3 - P_5||}{2 ||P_1 - P_4||}$$

```text
       P2    P3
      *     *
P1 *           * P4
      *     *
       P6    P5
```

1. **Capture**: Live video stream is captured frame-by-frame from the webcam.
2. **Detection**: The system detects the driver's face using a HOG + Linear SVM classifier.
3. **Landmarks**: Extracts 68 facial landmark coordinates using an Ensemble of Regression Trees.
4. **Computation**: Computes the Eye Aspect Ratio (EAR) using landmarks 37-42 (left eye) and 43-48 (right eye).
5. **Thresholding**: Monitors EAR over consecutive frames. If EAR falls below `0.20`, it signals eye closure.
6. **Alert**: If closure duration exceeds the fatigue threshold, the system triggers audio-visual alarms.

---

## 📊 System Workflow

```text
       ┌───────────────┐
       │  Video Input  │ (Webcam stream)
       └───────┬───────┘
               ▼
       ┌───────────────┐
       │Face Detection │ (HOG + Linear SVM)
       └───────┬───────┘
               ▼
       ┌───────────────┐
       │ Eye Detection │ (Dlib 68 Landmarks)
       └───────┬───────┘
               ▼
       ┌───────────────┐
       │EAR Calculation│ (Mathematical Formula)
       └───────┬───────┘
               ▼
       ┌─────────────────────┐
       │ Drowsiness Analysis │ (Temporal Thresholding)
       └───────┬─────────────┘
               ▼
       ┌───────────────┐
       │Alert Generated│ (Dashboard Audio/Visual Alert)
       └───────────────┘
```


## ⚙️ Installation & Setup

### Prerequisites
* **Node.js** (v18+)
* **Python** (3.9+) with `pip`
* **PostgreSQL** (v14+) running locally

---

### Step 1: Database Setup
1. Create a database in PostgreSQL named `ai_driver_drowsiness`.
2. Keep your PostgreSQL username and password ready.

---

### Step 2: Backend Setup (Node.js)
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Create a `.env` file in the `backend/` directory:
   ```env
   PORT=5001
   DATABASE_URL=postgres://<username>:<password>@localhost:5432/ai_driver_drowsiness
   JWT_SECRET=your_super_strong_secret_key
   CLIENT_URL=http://localhost:3000
   ```

---

### Step 3: Python ML Service Setup
1. Navigate to the Python service directory:
   ```bash
   cd backend/python_service
   ```
2. Create and activate a Virtual Environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
3. Install required libraries:
   ```bash
   pip install -r requirements.txt
   ```
4. **Download Dlib Landmarks Model**:
   * Download the `shape_predictor_68_face_landmarks.dat` file.
   * Place the `.dat` file inside the `backend/python_service/` directory.
5. Create a `.env` file inside `backend/python_service/`:
   ```env
   EAR_THRESHOLD=0.20
   NODE_BACKEND_URL=http://localhost:5001
   ```

---

### Step 4: Frontend Setup (React)
1. Navigate to the client folder:
   ```bash
   cd client
   ```
2. Install dependencies:
   ```bash
   npm install
   ```

---

## 🚀 Applications

* **Smart Vehicles**: Integration into modern autonomous and semi-autonomous cars.
* **Driver Assistance Systems**: Advanced Driver Assistance Systems (ADAS).
* **Fleet Management**: Monitoring truck, bus, and commercial drivers on long shifts.
* **Transportation Safety**: Reducing risk in logistics, railways, and public transit.

---

## 🔮 Future Enhancements

* **Mobile App Integration**: Creating a portable version for smartphones.
* **Night Vision Support**: Utilizing infrared cameras for low-light/night driving.
* **Yawning Detection**: Adding mouth landmark tracking for more comprehensive fatigue metrics.
* **Head Pose Estimation**: Tracking head slumping and distraction patterns.
* **IoT Vehicle Control**: Automatic vehicle slowing or emergency stopping via IoT integration.

---

## 📈 Expected Outcome

The system successfully detects driver drowsiness by monitoring eye blink patterns and provides immediate alerts, reducing the risk of fatigue-related accidents.

---

## 👩‍💻 Author

**Revathi Guggilla**
