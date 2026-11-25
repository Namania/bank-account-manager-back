from django.contrib import admin
from unfold.admin import ModelAdmin

from app.money import to_euros
from .forms import BudgetAdminForm, RecurringTransactionAdminForm


class RecurringTransactionAdmin(ModelAdmin):
    form = RecurringTransactionAdminForm
    list_display = ["comment", "owner", "sender", "receiver", "amount_euros", "frequency", "next_date", "is_active"]
    list_filter = ["frequency", "is_active"]
    readonly_fields = ["occurrences"]

    @admin.display(description="Amount (€)", ordering="amount")
    def amount_euros(self, obj):
        return to_euros(obj.amount)


class BudgetAdmin(ModelAdmin):
    form = BudgetAdminForm
    list_display = ["owner", "category", "amount_euros"]

    @admin.display(description="Monthly limit (€)", ordering="amount")
    def amount_euros(self, obj):
        return to_euros(obj.amount)
