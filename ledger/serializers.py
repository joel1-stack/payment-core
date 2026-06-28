from rest_framework import serializers
from .models import Account, Transaction, JournalEntry


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'name', 'account_type', 'balance', 'is_active']


class JournalEntrySerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = JournalEntry
        fields = ['id', 'transaction', 'account', 'account_name', 'entry_type', 'amount', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    entries = JournalEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'reference_id', 'reference_type', 'amount', 'description', 'created_at', 'entries']
