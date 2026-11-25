from django.db import models
from django.contrib import admin
from django.contrib.auth.models import User
from django.utils import timezone


class Account(models.Model):
    owners = models.ManyToManyField(User, blank=True)
    label = models.CharField(max_length=200, verbose_name="Title")
    # Integer cents. Converted to euros at the API and back-office boundaries.
    balance = models.BigIntegerField(default=0, verbose_name="Balance (cents)")
    create_at = models.DateTimeField(default=timezone.now, verbose_name="Create at")
    isActive = models.BooleanField(default=True, verbose_name="Is Active")
    # The single counterparty account for external credits and debits.
    # Its own balance is never tracked.
    is_bank = models.BooleanField(default=False, verbose_name="Is Bank")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_bank"], condition=models.Q(is_bank=True), name="unique_bank_account"
            ),
        ]

    @admin.display(
        boolean=True,
        description="Is Positive",
    )
    def isPositive(self):
        return self.balance >= 0

    def getName(self):
        return self.label if self.isActive else f"{self.label} (deleted)"

    def __str__(self):
        return str(self.label)
