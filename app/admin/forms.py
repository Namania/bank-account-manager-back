from django import forms
from unfold.widgets import UnfoldAdminDecimalFieldWidget

from app.models import Account, Budget, RecurringTransaction, Transaction
from app.money import to_cents, to_euros


class EuroFormField(forms.DecimalField):
    """Back-office money input: shown and typed in euros, saved in cents."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("widget", UnfoldAdminDecimalFieldWidget)
        super().__init__(**kwargs)

    def prepare_value(self, value):
        return to_euros(value) if isinstance(value, int) else value

    def clean(self, value):
        cleaned = super().clean(value)
        return None if cleaned is None else to_cents(cleaned)

    def has_changed(self, initial, data):
        return super().has_changed(None if initial is None else to_euros(initial), data)


class AccountAdminForm(forms.ModelForm):
    balance = EuroFormField(label="Balance (€)")

    class Meta:
        model = Account
        fields = ["owners", "label", "balance", "created_at", "is_active", "is_bank"]


class TransactionAdminForm(forms.ModelForm):
    amount = EuroFormField(label="Amount (€)", min_value=0)

    class Meta:
        model = Transaction
        fields = ["sender", "receiver", "amount", "comment", "category", "date"]


class RecurringTransactionAdminForm(forms.ModelForm):
    amount = EuroFormField(label="Amount (€)", min_value=0)

    class Meta:
        model = RecurringTransaction
        fields = ["owner", "sender", "receiver", "amount", "comment", "category", "frequency",
                  "start_date", "end_date", "next_date", "is_active"]


class BudgetAdminForm(forms.ModelForm):
    amount = EuroFormField(label="Monthly limit (€)", min_value=0)

    class Meta:
        model = Budget
        fields = ["owner", "category", "amount"]
