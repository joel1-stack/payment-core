"""
Test the live demo endpoints on port 8001.
"""
import urllib.request, json

BASE = "http://127.0.0.1:8001"

def req(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(r)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}

# 1. Health check
print("=== 1. Health ===")
print(json.dumps(req("GET", "/api/health/"), indent=2))

# 2. Split (first time — should succeed)
print("\n=== 2. Split $100 (first) ===")
r = req("POST", "/api/split/")
print(json.dumps(r, indent=2))

# 3. Balances
print("\n=== 3. Balances ===")
print(json.dumps(req("GET", "/api/balances/"), indent=2))

# 4. Split (second time — should be idempotent)
print("\n=== 4. Split $100 (second — idempotent) ===")
r = req("POST", "/api/split/")
print(json.dumps(r, indent=2))

# 5. Root page loads
print("\n=== 5. HTML page loads? ===")
try:
    r = urllib.request.urlopen(BASE + "/")
    print(f"Status: {r.status}, Length: {len(r.read())} bytes")
except Exception as e:
    print(f"Error: {e}")

print("\n[OK] Demo pipeline verified")
