import requests

BASE_URL = "http://localhost:5000"

endpoints = [
    "/api/status",
    "/api/incidents",
    "/api/alerts",
    "/api/self-healing",
    "/api/health-heatmap",
    "/api/historical-trends",
    "/api/anomaly-timeline",
    "/api/log-events",
    "/api/ai-recommendations",
    "/api/rca-insights",
    "/api/grouped-incidents",
    "/api/ml-insights",
    "/api/performance-metrics",
    "/api/self-healing-timeline",
]

def test_api():
    for ep in endpoints:
        url = BASE_URL + ep
        try:
            resp = requests.get(url)
            print(f"{ep}: {resp.status_code}")
            print(resp.json())
        except Exception as e:
            print(f"{ep}: ERROR - {e}")

# Test POST for /api/set-thresholds
threshold_url = BASE_URL + "/api/set-thresholds"
def test_set_thresholds():
    try:
        resp = requests.post(threshold_url, json={"cpu": 80, "mem": 85, "disk": 90})
        print(f"/api/set-thresholds: {resp.status_code}")
        print(resp.json())
    except Exception as e:
        print(f"/api/set-thresholds: ERROR - {e}")

if __name__ == "__main__":
    test_api()
    test_set_thresholds()
