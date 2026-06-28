"""
Complete merchant flow test: Pay -> Dashboard -> Withdraw
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from ledger.models import Merchant, Account, Transaction, JournalEntry
from ledger.services import SplitEngine

engine = SplitEngine()

# Create a merchant
user = User.objects.create_user("freshwash", password="test123")
merchant = Merchant.objects.create(user=user, business_name="FreshWash Laundry", phone="254712345678", platform_fee_percent=5)
print(f"Merchant: {merchant.business_name} (fee: {merchant.platform_fee_percent}%)")

# Simulate 3 customer payments
for i, amt in enumerate([1000, 2500, 750], 1):
    r = engine.merchant_split(merchant, f"MPESA_{i}", Decimal(str(amt)), f"Order #{i}")
    print(f"  Payment {i}: KES {amt} -> merchant earns KES {r['merchant_earns']}, fee KES {r['platform_fee']}")

# Dashboard
print("\n=== DASHBOARD ===")
dash = engine.merchant_dashboard(merchant)
for k, v in dash.items():
    print(f"  {k}: {v}")

# Withdraw
print("\n=== WITHDRAWAL ===")
w = engine.merchant_withdraw(merchant, "STL_001")
print(f"  Settled: KES {w['settled']}")

# Dashboard after withdrawal
print("\n=== AFTER WITHDRAWAL ===")
dash = engine.merchant_dashboard(merchant)
for k, v in dash.items():
    print(f"  {k}: {v}")

# Verify
earnings = Account.objects.get(name=f"Earnings_{merchant.id}")
pool = Account.objects.get(name=f"Pool_{merchant.id}")
fee = Account.objects.get(name="Platform_Fees")
print("\n=== LEDGER VERIFICATION ===")
print(f"  Pool (Asset): KES {pool.balance}")
print(f"  Earnings (Liability): KES {earnings.balance}")
print(f"  Fees (Revenue): KES {fee.balance}")
print(f"  Transactions: {Transaction.objects.count()}")
print(f"  Journal Entries: {JournalEntry.objects.count()}")
