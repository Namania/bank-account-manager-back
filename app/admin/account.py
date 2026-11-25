from django.contrib import admin
from unfold.admin import ModelAdmin

from app.money import to_euros
from .forms import AccountAdminForm


class AccountAdmin(ModelAdmin):
    form = AccountAdminForm
    list_display = ["pk", "label", "balance_euros", "created_at", "is_positive", "is_active", "is_bank"]

    @admin.display(description="Balance (€)", ordering="balance")
    def balance_euros(self, obj):
        return to_euros(obj.balance)
