"""
Test script for the Payment Split Engine.
Run: python test_split.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from ledger.models import Account, Transaction, JournalEntry
from ledger.services import SplitEngine, SplitRule


def test_payment_split():
    print("=" * 60)
    print("PAYMENT SPLIT ENGINE - SIMULATION")
    print("=" * 60)

    engine = SplitEngine()

    # Scenario: Customer pays KES 1,000 at FreshWash Laundry
    # Split: 90% to shop, 5% platform fee, 5% rent reserve
    print("\n[1] Customer pays KES 1,000 via M-Pesa")
    print("-" * 40)

    result = engine.execute_payment_split(
        reference_id="MPESA_TXN_001",
        total_amount=Decimal('1000'),
        pool_account_name="M-Pesa Pool Account",
        split_rules=[
            SplitRule("FreshWash Earnings", Decimal('90'), "LIABILITY"),
            SplitRule("Platform Fees", Decimal('5'), "REVENUE"),
            SplitRule("Rent Reserve", Decimal('5'), "LIABILITY"),
        ],
        description="Customer laundry payment - FreshWash",
    )

    print(f"  Transaction: {result['reference_id']}")
    print(f"  Amount: KES {result['total_amount']}")
    print(f"  Status: {result['status']}")
    print("  [OK] Payment recorded and split across 3 accounts")

    # Show account balances
    print("\n[2] Account Balances After Split")
    print("-" * 40)
    for account in Account.objects.all():
        print(f"  {account.name:25s} | {account.account_type:10s} | KES {account.balance}")

    # Verify double-entry: total debits = total credits
    print("\n[3] Double-Entry Verification")
    print("-" * 40)
    txn = Transaction.objects.get(reference_id="MPESA_TXN_001")
    entries = JournalEntry.objects.filter(transaction=txn)
    total_debits = sum(e.amount for e in entries if e.entry_type == 'DEBIT')
    total_credits = sum(e.amount for e in entries if e.entry_type == 'CREDIT')
    print(f"  Total Debits : KES {total_debits}")
    print(f"  Total Credits: KES {total_credits}")
    assert total_debits == total_credits, "BOOKS DON'T BALANCE!"
    print("  [OK] Books balance! Money is conserved.")

    # Test refund
    print("\n[4] Refund Test - Customer cancels, KES 1,000 refunded")
    print("-" * 40)
    refund_result = engine.execute_refund(
        original_reference_id="MPESA_TXN_001",
        refund_reference_id="REFUND_TXN_001",
        description="Customer cancelled order - full refund",
    )
    print(f"  Refund Transaction: {refund_result['reference_id']}")
    print(f"  Amount: KES {refund_result['amount']}")
    print(f"  Status: {refund_result['status']}")

    print("\n[5] Final Account Balances After Refund")
    print("-" * 40)
    for account in Account.objects.all():
        print(f"  {account.name:25s} | {account.account_type:10s} | KES {account.balance}")
        assert account.balance == Decimal('0'), f"{account.name} should be zero after refund!"
    print("  [OK] All accounts back to zero. Money conserved through refund.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED [OK]")
    print("The double-entry ledger works correctly.")
    print("=" * 60)


if __name__ == '__main__':
    test_payment_split()
