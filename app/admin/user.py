from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm


class UserAdmin(BaseUserAdmin, ModelAdmin):
    """Django's user admin, restyled: unfold needs its own forms to theme the password fields."""
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
