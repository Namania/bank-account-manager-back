from django.contrib.auth.models import User
from django.db import models

from .category import Category


class Budget(models.Model):
    """What a user plans to spend at most in a category each month."""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="budgets")
    amount = models.BigIntegerField(verbose_name="Monthly limit (cents)")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "category"], name="unique_budget_per_category"),
        ]

    def __str__(self):
        return f"{self.owner} / {self.category}"
