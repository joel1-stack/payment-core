from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models import F
from .models import Account, Transaction, JournalEntry, Merchant


class SplitEngine:
    """Core double-entry split engine."""

    @staticmethod
    def merchant_split(merchant: Merchant, reference_id: str, amount: Decimal, description: str = "") -> dict:
        """
        Split a payment for a specific merchant.
        Auto-creates merchant accounts and deducts platform fee.
        """
        fee_pct = merchant.platform_fee_percent / Decimal('100')
        fee_amount = (amount * fee_pct).quantize(Decimal('0.01'))
        merchant_amount = amount - fee_amount

        pool_acc, _ = Account.objects.get_or_create(
            name=f"Pool_{merchant.id}", defaults={'account_type': 'ASSET', 'balance': Decimal('0.00')}
        )
        earnings_acc, _ = Account.objects.get_or_create(
            name=f"Earnings_{merchant.id}", defaults={'account_type': 'LIABILITY', 'balance': Decimal('0.00')}
        )
        fee_acc, _ = Account.objects.get_or_create(
            name="Platform_Fees", defaults={'account_type': 'REVENUE', 'balance': Decimal('0.00')}
        )

        txn = Transaction.objects.create(
            reference_id=reference_id, reference_type='PAYMENT_IN',
            amount=amount, description=description,
        )

        with db_transaction.atomic():
            JournalEntry.objects.create(transaction=txn, account=pool_acc, entry_type='DEBIT', amount=amount)
            JournalEntry.objects.create(transaction=txn, account=earnings_acc, entry_type='CREDIT', amount=merchant_amount)
            JournalEntry.objects.create(transaction=txn, account=fee_acc, entry_type='CREDIT', amount=fee_amount)
            for acc, delta in [(pool_acc, amount), (earnings_acc, merchant_amount), (fee_acc, fee_amount)]:
                Account.objects.filter(pk=acc.pk).update(balance=F('balance') + delta)

        return {"reference_id": reference_id, "total": str(amount), "merchant_earns": str(merchant_amount), "platform_fee": str(fee_amount)}

    @staticmethod
    def merchant_withdraw(merchant: Merchant, reference_id: str) -> dict:
        """
        Merchant withdraws available earnings. Moves liability to zero.
        In production this would also call M-Pesa B2C API.
        """
        earnings_acc = Account.objects.get(name=f"Earnings_{merchant.id}")
        amount = earnings_acc.balance
        if amount <= 0:
            raise ValueError("No balance to withdraw")

        pool_acc = Account.objects.get(name=f"Pool_{merchant.id}")

        txn = Transaction.objects.create(
            reference_id=reference_id, reference_type='SETTLEMENT',
            amount=amount, description=f"Settlement to {merchant.business_name}",
        )

        with db_transaction.atomic():
            JournalEntry.objects.create(transaction=txn, account=earnings_acc, entry_type='DEBIT', amount=amount)
            JournalEntry.objects.create(transaction=txn, account=pool_acc, entry_type='CREDIT', amount=amount)
            Account.objects.filter(pk=earnings_acc.pk).update(balance=F('balance') - amount)
            Account.objects.filter(pk=pool_acc.pk).update(balance=F('balance') - amount)

        return {"reference_id": reference_id, "settled": str(amount), "status": "paid_out"}

    @staticmethod
    def merchant_dashboard(merchant: Merchant) -> dict:
        """Returns user-friendly dashboard data for a merchant."""
        try:
            earnings = Account.objects.get(name=f"Earnings_{merchant.id}")
            pool = Account.objects.get(name=f"Pool_{merchant.id}")
        except Account.DoesNotExist:
            return {"business": merchant.business_name, "total_sales": "0.00", "available": "0.00", "fees_paid": "0.00"}

        fee_acc = Account.objects.get(name="Platform_Fees")
        total_sales = pool.balance + earnings.balance
        return {
            "business": merchant.business_name,
            "total_sales": str(total_sales),
            "available": str(earnings.balance),
            "fees_paid": str(fee_acc.balance),
            "currency": "KES",
        }
