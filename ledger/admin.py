from django.contrib import admin
from .models import Account, Transaction, JournalEntry, Merchant


class JournalEntryInline(admin.TabularInline):
    model = JournalEntry
    readonly_fields = ['created_at']
    extra = 0


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'phone', 'platform_fee_percent', 'created_at']
    search_fields = ['business_name', 'phone']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_type', 'balance', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['name']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['reference_id', 'reference_type', 'amount', 'created_at']
    list_filter = ['reference_type']
    search_fields = ['reference_id']
    inlines = [JournalEntryInline]


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['transaction', 'account', 'entry_type', 'amount', 'created_at']
    list_filter = ['entry_type']
    search_fields = ['transaction__reference_id', 'account__name']
