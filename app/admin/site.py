from unfold.admin import ModelAdmin

from app.models import SiteSetting


class SiteSettingAdmin(ModelAdmin):
    """A single row: it can be edited, never added twice or deleted."""
    list_display = ["__str__", "maintenance", "maintenance_message"]

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
