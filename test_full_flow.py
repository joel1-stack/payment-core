"""
Complete M-Pesa + Ledger Flow Simulation

Simulates the full pipeline:
  Customer pays via M-Pesa STK Push
  -> M-Pesa callback hits our server
  -> Ledger records the split
  -> Merchant checks dashboard
  -> Merchant withdraws to their phone via B2C

Run: python test_full_flow.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from django.test import RequestFactory
from ledger.models import Merchant, Account, Transaction, JournalEntry
from ledger.services import SplitEngine

engine = SplitEngine()

print("=" * 65)
print("  M-PESA + LEDGER - FULL PIPELINE SIMULATION")
print("=" * 65)

# ─────────────────────────────────────────────────────
# 1. CREATE A MERCHANT
# ─────────────────────────────────────────────────────
user = User.objects.create_user("freshwash", password="123")
merchant = Merchant.objects.create(
    user=user,
    business_name="FreshWash Laundry",
    phone="254712345678",
    platform_fee_percent=5,  # 5% platform fee
)
print(f"\n[1] Merchant onboarded: {merchant.business_name}")
print(f"    Phone: {merchant.phone} | Platform fee: {merchant.platform_fee_percent}%")

# ─────────────────────────────────────────────────────
# 2. SIMULATE CUSTOMER PAYMENTS VIA M-PESA
# ─────────────────────────────────────────────────────
print(f"\n[2] Customers paying via M-Pesa STK Push...")
print(f"    {'='*45}")

payments = [
    ("MPESA_A1", 1000, "Order #101 - 3kg laundry"),
    ("MPESA_A2", 2500, "Order #102 - Dry cleaning"),
    ("MPESA_A3", 750,  "Order #103 - Ironing only"),
    ("MPESA_A4", 5000, "Order #104 - Bulk hotel linen"),
]

total_collected = Decimal('0')
total_fees = Decimal('0')
total_merchant = Decimal('0')

for ref, amt, desc in payments:
    result = engine.merchant_split(merchant, ref, Decimal(str(amt)), desc)
    total_collected += Decimal(result['total'])
    total_fees += Decimal(result['platform_fee'])
    total_merchant += Decimal(result['merchant_earns'])
    print(f"    KES {amt:>6} paid | Merchant: KES {result['merchant_earns']:>6} | Fee: KES {result['platform_fee']:>5}")

print(f"    {'='*45}")
print(f"    TOTAL:     KES {total_collected:>8}")
print(f"    MERCHANT:  KES {total_merchant:>8}")
print(f"    FEES:      KES {total_fees:>8}")

# ─────────────────────────────────────────────────────
# 3. SHOW THE DASHBOARD (What the merchant sees)
# ─────────────────────────────────────────────────────
print(f"\n[3] Merchant Dashboard")
print(f"    {'='*45}")
dash = engine.merchant_dashboard(merchant)
for k, v in dash.items():
    print(f"    {k:15s}: {v}")

# ─────────────────────────────────────────────────────
# 4. VERIFY THE LEDGER (Double-entry check)
# ─────────────────────────────────────────────────────
print(f"\n[4] Ledger Verification")
print(f"    {'='*45}")

# Check accounts
earnings = Account.objects.get(name=f"Earnings_{merchant.id}")
pool = Account.objects.get(name=f"Pool_{merchant.id}")
fee_account = Account.objects.get(name="Platform_Fees")

# Verify debits = credits
all_entries = JournalEntry.objects.all()
total_debits = sum(e.amount for e in all_entries if e.entry_type == 'DEBIT')
total_credits = sum(e.amount for e in all_entries if e.entry_type == 'CREDIT')
balanced = total_debits == total_credits

print(f"    Pool (Asset):           KES {str(pool.balance):>8}")
print(f"    Earnings (Liability):   KES {str(earnings.balance):>8}")
print(f"    Fees (Revenue):         KES {str(fee_account.balance):>8}")
print(f"    Total Debits:           KES {str(total_debits):>8}")
print(f"    Total Credits:          KES {str(total_credits):>8}")
print(f"    Books Balance:          {'YES [OK]' if balanced else 'NO [FAIL]'}")
print(f"    Transactions:           {Transaction.objects.count()}")
print(f"    Journal Entries:        {JournalEntry.objects.count()}")

# ─────────────────────────────────────────────────────
# 5. SIMULATE WITHDRAWAL (B2C)
# ─────────────────────────────────────────────────────
print(f"\n[5] Merchant Withdraws to M-Pesa")
print(f"    {'='*45}")

available = Decimal(dash['available'])
print(f"    Available: KES {available}")
if available > 0:
    withdrawal = engine.merchant_withdraw(merchant, "STL_001")
    print(f"    Settlement ref: {withdrawal['reference_id']}")
    print(f"    Amount sent:    KES {withdrawal['settled']}")
    print(f"    Status:         {withdrawal['status']}")
    print(f"    In production, this calls M-Pesa B2C API to push real money.")

# ─────────────────────────────────────────────────────
# 6. FINAL STATE
# ─────────────────────────────────────────────────────
print(f"\n[6] Final State After Withdrawal")
print(f"    {'='*45}")
dash = engine.merchant_dashboard(merchant)
for k, v in dash.items():
    print(f"    {k:15s}: {v}")

# Show cumulative platform revenue
print(f"\n{'='*65}")
print(f"  PLATFORM REVENUE: KES {fee_account.balance}")
print(f"  (This is what you earned from FreshWash's payments)")
print(f"{'='*65}")
