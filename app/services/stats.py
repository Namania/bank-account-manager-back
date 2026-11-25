"""Income, expense and balance history over a set of accounts.

"Expense" is money leaving the set, "income" is money entering it. A transfer
between two accounts of the set is neither. Opening transactions are not income.
"""
import datetime

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth

from app.models import Account, Transaction
from app.money import to_euros


def _flows(account_ids):
    inside_sender = Q(sender_id__in=account_ids)
    inside_receiver = Q(receiver_id__in=account_ids)
    regular = Q(is_opening=False)
    return {
        "expense": Sum("amount", filter=inside_sender & ~inside_receiver & regular, default=0),
        "income": Sum("amount", filter=inside_receiver & ~inside_sender & regular, default=0),
    }


def _touching(account_ids):
    return Transaction.objects.filter(Q(sender_id__in=account_ids) | Q(receiver_id__in=account_ids))


def _in_range(queryset, date_from, date_to):
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    if date_to:
        queryset = queryset.filter(date__lte=date_to)
    return queryset


def by_category(account_ids, date_from=None, date_to=None):
    rows = (
        _in_range(_touching(account_ids), date_from, date_to)
        .order_by()
        .values("category_id", "category__label", "category__color")
        .annotate(**_flows(account_ids))
    )
    result = [
        {
            "category": row["category_id"],
            "label": row["category__label"],
            "color": row["category__color"],
            "expense": str(to_euros(row["expense"])),
            "income": str(to_euros(row["income"])),
        }
        for row in rows
        if row["expense"] or row["income"]
    ]
    return sorted(result, key=lambda row: (-float(row["expense"]), -float(row["income"])))


def _month_range(first, last):
    month = first.replace(day=1)
    while month <= last:
        yield month
        month = (month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)


def monthly(account_ids, date_from=None, date_to=None, today=None):
    """One row per month, oldest first, with the total balance at the end of each month.

    The balance history is rebuilt backwards from the current balances, so a
    balance edited by hand in the back-office shifts the whole curve.
    """
    today = today or datetime.date.today()
    inside_sender = Q(sender_id__in=account_ids)
    inside_receiver = Q(receiver_id__in=account_ids)
    per_month = {
        row["month"]: row
        for row in _touching(account_ids)
        .order_by()
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            credit=Sum("amount", filter=inside_receiver, default=0),
            debit=Sum("amount", filter=inside_sender, default=0),
            **_flows(account_ids),
        )
    }
    if not per_month:
        return []

    first = date_from or min(per_month)
    last = date_to or max(today, *per_month)
    balance = Account.objects.filter(pk__in=account_ids).aggregate(total=Sum("balance", default=0))["total"]
    # Undo everything that happened after the requested range.
    for month, row in per_month.items():
        if month > last.replace(day=1):
            balance -= row["credit"] - row["debit"]

    result = []
    for month in reversed(list(_month_range(first, last))):
        row = per_month.get(month, {"credit": 0, "debit": 0, "income": 0, "expense": 0})
        result.append({
            "month": month.strftime("%Y-%m"),
            "income": str(to_euros(row["income"])),
            "expense": str(to_euros(row["expense"])),
            "net": str(to_euros(row["income"] - row["expense"])),
            "balance": str(to_euros(balance)),
        })
        balance -= row["credit"] - row["debit"]
    return result[::-1]
