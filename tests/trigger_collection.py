import requests
import json
import time

def trigger():
    url = "http://127.0.0.1:5001/api/tasks/collect/start"
    payload = {
        "start_date": "2025-11-28",
        "end_date": "2025-11-28",
        "filter_by_handicap": True,
        "skip_cached": True,
        "workers": 3
    }
    try:
        print(f"Sending request to {url}...")
        resp = requests.post(url, json=payload, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Wait a bit for server to start if run immediately after
    time.sleep(2)
    trigger()
