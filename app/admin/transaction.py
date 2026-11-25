from django.contrib import admin
from unfold.admin import ModelAdmin

from app.money import to_euros
from .forms import TransactionAdminForm


class TransactionAdmin(ModelAdmin):
    form = TransactionAdminForm
    list_display = ["sender", "receiver", "amount_euros", "comment", "category", "create_at"]
    readonly_fields = ["create_at"]

    @admin.display(description="Amount (€)", ordering="amount")
    def amount_euros(self, obj):
        return to_euros(obj.amount)
