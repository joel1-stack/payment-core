from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models import F
from .models import Account, Transaction, JournalEntry


class SplitRule:
    def __init__(self, account_name: str, percentage: Decimal, account_type: str):
        self.account_name = account_name
        self.percentage = percentage
        self.account_type = account_type


class SplitEngine:
    """
    The core split engine. Takes a payment and divides it across accounts
    using double-entry bookkeeping.
    """

    @staticmethod
    def execute_payment_split(
        reference_id: str,
        total_amount: Decimal,
        pool_account_name: str = "M-Pesa Pool Account",
        split_rules: list[SplitRule] | None = None,
        description: str = "",
    ) -> dict:
        """
        Execute a payment split.

        Example split_rules:
            SplitRule("FreshWash Earnings", Decimal('95'), "LIABILITY")
            SplitRule("Platform Fees", Decimal('5'), "REVENUE")
        """
        if split_rules is None:
            split_rules = []

        total_pct = sum(r.percentage for r in split_rules)
        if total_pct != Decimal('100'):
            raise ValueError(f"Split percentages must sum to 100, got {total_pct}")

        # Get or create the pool account
        pool_account, _ = Account.objects.get_or_create(
            name=pool_account_name,
            defaults={'account_type': 'ASSET', 'balance': Decimal('0.00')}
        )

        # Get or create split target accounts
        target_accounts = []
        for rule in split_rules:
            account, _ = Account.objects.get_or_create(
                name=rule.account_name,
                defaults={'account_type': rule.account_type, 'balance': Decimal('0.00')}
            )
            target_accounts.append((account, rule.percentage))

        # Create the transaction record
        txn = Transaction.objects.create(
            reference_id=reference_id,
            reference_type='PAYMENT_IN',
            amount=total_amount,
            description=description,
        )

        with db_transaction.atomic():
            # Debit the pool account (money comes in)
            JournalEntry.objects.create(
                transaction=txn,
                account=pool_account,
                entry_type='DEBIT',
                amount=total_amount,
            )
            Account.objects.filter(pk=pool_account.pk).update(balance=F('balance') + total_amount)

            # Credit each target account
            for account, pct in target_accounts:
                split_amount = (total_amount * pct / Decimal('100')).quantize(Decimal('0.01'))
                JournalEntry.objects.create(
                    transaction=txn,
                    account=account,
                    entry_type='CREDIT',
                    amount=split_amount,
                )
                Account.objects.filter(pk=account.pk).update(balance=F('balance') + split_amount)

        return {
            'transaction_id': txn.id,
            'reference_id': txn.reference_id,
            'total_amount': str(total_amount),
            'status': 'completed',
        }

    @staticmethod
    def execute_refund(
        original_reference_id: str,
        refund_reference_id: str,
        description: str = "",
    ) -> dict:
        """Reverse a payment by flipping each journal entry by its own amount."""
        original_txn = Transaction.objects.get(reference_id=original_reference_id)
        entries = JournalEntry.objects.filter(transaction=original_txn)

        if not entries.exists():
            raise ValueError(f"No entries found for transaction {original_reference_id}")

        total_refund = original_txn.amount
        refund_txn = Transaction.objects.create(
            reference_id=refund_reference_id,
            reference_type='REFUND',
            amount=total_refund,
            description=description,
        )

        with db_transaction.atomic():
            for entry in entries:
                reversed_type = 'CREDIT' if entry.entry_type == 'DEBIT' else 'DEBIT'
                JournalEntry.objects.create(
                    transaction=refund_txn,
                    account=entry.account,
                    entry_type=reversed_type,
                    amount=entry.amount,
                )
                Account.objects.filter(pk=entry.account.pk).update(
                    balance=F('balance') - entry.amount
                )

        return {
            'transaction_id': refund_txn.id,
            'reference_id': refund_txn.reference_id,
            'amount': str(total_refund),
            'status': 'refunded',
        }
