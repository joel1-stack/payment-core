"""
The No-Internet Test: Proves the Engine Works Without Any External API.
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from ledger.models import Merchant, Account, Transaction, JournalEntry
from ledger.services import SplitEngine
from providers.mock_provider import MockProvider

engine = SplitEngine()
provider = MockProvider()

print("=" * 60)
print("  THE NO-INTERNET TEST")
print("  Proving the engine works without any payment API")
print("=" * 60)

# 1. Create merchant
user = User.objects.create_user("demo", password="123")
merchant = Merchant.objects.create(user=user, business_name="Demo Shop", phone="254700000000", platform_fee_percent=5)
print(f"\n[1] Merchant: {merchant.business_name}")

# 2. Trigger split using MockProvider (no internet)
print(f"\n[2] Mock payment of KES 1000 via MockProvider...")
payment = provider.charge(amount=Decimal("1000"), currency="KES", customer_ref="254712345678")
result = engine.merchant_split(merchant, payment['reference'], Decimal("1000"), "No-internet demo")
print(f"    Reference: {payment['reference']}")
print(f"    Provider:  {payment['provider']}")
print(f"    Merchant:  KES {result['merchant_earns']}")
print(f"    Platform:  KES {result['platform_fee']}")

# 3. Idempotency test: same reference again
print(f"\n[3] Idempotency test (same reference)...")
result2 = engine.merchant_split(merchant, payment['reference'], Decimal("1000"), "Should be rejected")
print(f"    Idempotent: {result2.get('idempotent', False)}")

# 4. Another mock payment
print(f"\n[4] Mock payment of KES 2500...")
payment2 = provider.charge(amount=Decimal("2500"), currency="KES", customer_ref="254798765432")
engine.merchant_split(merchant, payment2['reference'], Decimal("2500"), "Second order")

# 5. Dashboard
print(f"\n[5] Merchant Dashboard")
dash = engine.merchant_dashboard(merchant)
for k, v in dash.items():
    print(f"    {k:15s}: {v}")

# 6. Balance verification
print(f"\n[6] Ledger Balance Check")
debits = sum(e.amount for e in JournalEntry.objects.filter(entry_type='DEBIT'))
credits = sum(e.amount for e in JournalEntry.objects.filter(entry_type='CREDIT'))
print(f"    Debits:  KES {debits}")
print(f"    Credits: KES {credits}")
print(f"    Balanced: {debits == credits}")

# 7. Withdraw via MockProvider
print(f"\n[7] Mock withdrawal...")
w = engine.merchant_withdraw(merchant, "STL_DEMO_001")
payout = provider.payout(amount=Decimal(w['settled']), recipient=merchant.phone)
print(f"    Ledger:   {w['status']} - KES {w['settled']}")
print(f"    Payout:   {payout['status']} via {payout['provider']}")

# 8. Final state
print(f"\n[8] Final State")
dash = engine.merchant_dashboard(merchant)
for k, v in dash.items():
    print(f"    {k:15s}: {v}")

print(f"\n{'='*60}")
print(f"  ZERO internet calls made. Engine works in isolation.")
print(f"{'='*60}")
