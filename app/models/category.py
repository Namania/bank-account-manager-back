from django.contrib.auth.models import User
from django.db import models
from colorfield.fields import ColorField


class Category(models.Model):
    label = models.CharField(max_length=200)
    color = ColorField(verbose_name="Color", default="#007bff")
    # No owner: shared by everyone and managed by staff. Otherwise private to its owner.
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name="categories")

    def __str__(self):
        return str(self.label)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
