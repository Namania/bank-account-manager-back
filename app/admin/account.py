from django.contrib import admin

from app.money import to_euros
from .forms import AccountAdminForm


class AccountAdmin(admin.ModelAdmin):
    form = AccountAdminForm
    list_display = ["pk", "label", "balance_euros", "create_at", "isPositive", "isActive", "is_bank"]

    @admin.display(description="Balance (€)", ordering="balance")
    def balance_euros(self, obj):
        return to_euros(obj.balance)
