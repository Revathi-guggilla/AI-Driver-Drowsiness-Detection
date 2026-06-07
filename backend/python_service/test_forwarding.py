import requests
import json

url = "http://localhost:8001/api/ai/webcam-log"
payload = {
    "user_email": "revathi@gmail.com",
    "ear_value": 0.25,
    "status": "AWAKE",
    "blink_rate": 0,
    "confidence": 0.8,
    "timestamp": "2026-03-08T21:00:00"
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
