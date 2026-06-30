"""
Hit the live merchant API to see the full flow.
"""
import urllib.request, json

BASE = "http://127.0.0.1:8000/api"

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

# Create a merchant via django admin won't work here, so we use the test run.
# Instead, hit the existing endpoints.
print("=== Existing Accounts ===")
print(json.dumps(req("GET", "/accounts/"), indent=2)[:500])
print("\n=== Existing Transactions ===")
print(json.dumps(req("GET", "/transactions/"), indent=2)[:500])
print("\n=== Existing Journal Entries ===")
print(json.dumps(req("GET", "/entries/"), indent=2)[:500])
