"""Who may see and use what. Single source of truth for the API querysets."""
from django.db.models import Q

from app.models import Account


def usable_accounts(user):
    """Accounts a user may put on either side of a transaction."""
    if user.is_staff:
        return Account.objects.all()
    return Account.objects.filter(Q(owners=user, isActive=True) | Q(is_bank=True)).distinct()
