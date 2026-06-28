from django.db import models
from django.core.exceptions import ValidationError

class Account(models.Model):
    ACCOUNT_TYPES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
    ]

    name = models.CharField(max_length=100, unique=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.account_type}) - KES {self.balance}"


class Transaction(models.Model):
    REFERENCE_TYPES = [
        ('PAYMENT_IN', 'Payment Received'),
        ('SPLIT', 'Revenue Split'),
        ('SETTLEMENT', 'Bank Payout'),
        ('REFUND', 'Refund'),
        ('FEE', 'Platform Fee Deduction'),
    ]

    reference_id = models.CharField(max_length=100, unique=True)
    reference_type = models.CharField(max_length=20, choices=REFERENCE_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.reference_id} - KES {self.amount}"


class JournalEntry(models.Model):
    ENTRY_TYPES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='entries')
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['transaction', 'account'], name='unique_entry_per_tx_account')
        ]

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Journal entry amount must be greater than zero.")

    def __str__(self):
        return f"{self.transaction.reference_id} | {self.account.name} | {self.entry_type} | KES {self.amount}"
