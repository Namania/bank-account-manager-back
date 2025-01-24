from app.models import Account
from django.db.models import Q

def getAccounts(user):
    return Account.objects.filter(Q(owner=user) & Q(isActive=True)).order_by("balance").reverse()