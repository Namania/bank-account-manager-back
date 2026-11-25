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
    create_at = models.DateTimeField("Create at", default=timezone.now)

    def __str__(self):
        if self.sender is None or self.receiver is None:
            return "deleted_account"
        return f"{self.sender.label} => {self.receiver.label}"
