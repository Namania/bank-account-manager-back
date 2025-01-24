from django.contrib import admin
from .transaction import TransactionInline

class AccountAdmin(admin.ModelAdmin):
    list_display = ["pk", "label", "create_at", "isPositive", "isActive"]
    fields = ["owner", "label", "balance", "create_at", "isActive"]
    inlines = [TransactionInline]