import sys, requests
API_URL = "https://data.police.uk/api/crimes-street/all-crime"
def test_api_reachable():
    print("Checking Police UK API...")
    try:
        resp = requests.get(API_URL, params={"lat": 53.745, "lng": -0.336, "date": "2024-05"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        assert isinstance(data, list) and len(data) > 0 and "category" in data[0]
        print(f"  ✅ API OK — {len(data):,} records returned")
    except Exception as e:
        print(f"  ❌ FAILED — {e}"); sys.exit(1)
if __name__ == "__main__":
    test_api_reachable()
    print("API health check passed.")
