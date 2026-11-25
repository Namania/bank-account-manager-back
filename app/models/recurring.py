from django.contrib.auth.models import User
from django.db import models

from .account import Account
from .category import Category


class RecurringTransaction(models.Model):
    """A rule that creates the same transaction at a fixed rhythm (rent, salary, subscriptions)."""

    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recurring_transactions")
    sender = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    receiver = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    amount = models.BigIntegerField(verbose_name="Amount (cents)")
    comment = models.CharField(max_length=200, null=True, blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    # Every occurrence is computed from start_date, so a rule set on the 31st
    # comes back to the 31st after a shorter month.
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_date = models.DateField(null=True, blank=True)
    occurrences = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.comment or 'Recurring'} ({self.frequency})"
