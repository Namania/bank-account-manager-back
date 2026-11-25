from django.utils import timezone
from django.db import models

from .account import Account
from .category import Category


class Transaction(models.Model):
    sender = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="sender")
    receiver = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="receiver")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="category")
    # Integer cents, always positive: the direction is given by sender and receiver.
    amount = models.BigIntegerField(default=0, verbose_name="Amount (cents)")
    comment = models.CharField(max_length=200, null=True, blank=True)
    # When the money moved, as opposed to when the row was typed in.
    date = models.DateField("Operation date", default=timezone.localdate, db_index=True)
    created_at = models.DateTimeField("Created at", default=timezone.now, editable=False)
    # The initial balance of an account, recorded as its first transaction.
    # Kept out of income and expense statistics.
    is_opening = models.BooleanField(default=False)
    # The rule that generated this transaction, if any.
    recurring = models.ForeignKey("app.RecurringTransaction", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="generated", editable=False)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        if self.sender is None or self.receiver is None:
            return "deleted_account"
        return f"{self.sender.label} => {self.receiver.label}"
