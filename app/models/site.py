from django.db import models


class SiteSetting(models.Model):
    """Application-wide switches. There is a single row, with primary key 1."""
    maintenance = models.BooleanField(
        default=False,
        help_text="When on, the API answers 503 to everything except /health/, the login and the back-office.",
    )
    maintenance_message = models.CharField(max_length=200, blank=True, help_text="Shown to users during maintenance.")

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "Site settings"
