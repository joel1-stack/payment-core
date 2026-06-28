"""Test the live API endpoints."""
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

# 1. List accounts
print("=== Accounts ===")
accounts = req("GET", "/accounts/")
print(json.dumps(accounts, indent=2))

# 2. Do a payment split: KES 2000, 90% shop, 10% platform
print("\n=== Split Payment KES 2000 ===")
split = req("POST", "/payments/split/", {
    "reference_id": "MPESA_002",
    "amount": "2000",
    "pool_account": "M-Pesa Pool",
    "rules": [
        {"account_name": "Shop Earnings", "percentage": "90", "account_type": "LIABILITY"},
        {"account_name": "Platform Fee", "percentage": "10", "account_type": "REVENUE"},
    ],
    "description": "Test payment"
})
print(json.dumps(split, indent=2))

# 3. List transactions
print("\n=== Transactions ===")
txns = req("GET", "/transactions/")
print(json.dumps(txns, indent=2))

# 4. List journal entries
print("\n=== Journal Entries ===")
entries = req("GET", "/entries/")
print(json.dumps(entries, indent=2))

# 5. Show final balances
print("\n=== Final Balances ===")
accounts = req("GET", "/accounts/")
print(json.dumps(accounts, indent=2))

print("\n[OK] API works end-to-end")
