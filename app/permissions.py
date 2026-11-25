"""Who may see and use what. Single source of truth for the API querysets."""
from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, BasePermission

from app.models import Account, Category


def usable_accounts(user):
    """Accounts a user may put on either side of a transaction."""
    if user.is_staff:
        return Account.objects.all()
    return Account.objects.filter(Q(owners=user, isActive=True) | Q(is_bank=True)).distinct()


def visible_categories(user):
    """Shared categories plus the user's own."""
    if user.is_staff:
        return Category.objects.all()
    return Category.objects.filter(Q(owner=None) | Q(owner=user))


class IsOwnerOrStaffOrReadOnly(BasePermission):
    """Anyone may read an object; only its owner or staff may change it.

    Ownerless objects are shared, so only staff may change them.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or request.user.is_staff:
            return True
        return obj.owner_id is not None and obj.owner_id == request.user.id
