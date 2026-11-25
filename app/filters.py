"""Query-string filters for transactions, shared by the list and the statistics."""
import datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend

from app.money import to_cents

ORDERINGS = {"date", "-date", "amount", "-amount", "created_at", "-created_at"}


def parse_date(params, name):
    raw = params.get(name)
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({name: "Expected a date as YYYY-MM-DD."}) from exc


def parse_int(params, name):
    raw = params.get(name)
    if not raw:
        return None
    if not raw.isascii() or not raw.isdigit():
        raise ValidationError({name: "Expected an id."})
    return int(raw)


def parse_cents(params, name):
    raw = params.get(name)
    if not raw:
        return None
    try:
        return to_cents(Decimal(raw))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError({name: "Expected an amount in euros, such as 10.50."}) from exc


class TransactionFilterBackend(BaseFilterBackend):
    """date_from, date_to, category (id or "none"), account, amount_min, amount_max, search, ordering.

    Filters only ever narrow the queryset the view already restricted to the caller.
    """

    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        date_from, date_to = parse_date(params, "date_from"), parse_date(params, "date_to")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        if params.get("category") == "none":
            queryset = queryset.filter(category__isnull=True)
        elif (category := parse_int(params, "category")) is not None:
            queryset = queryset.filter(category_id=category)

        if (account := parse_int(params, "account")) is not None:
            queryset = queryset.filter(Q(sender_id=account) | Q(receiver_id=account))

        if (amount_min := parse_cents(params, "amount_min")) is not None:
            queryset = queryset.filter(amount__gte=amount_min)
        if (amount_max := parse_cents(params, "amount_max")) is not None:
            queryset = queryset.filter(amount__lte=amount_max)

        if search := params.get("search"):
            queryset = queryset.filter(comment__icontains=search)

        if ordering := params.get("ordering"):
            if ordering not in ORDERINGS:
                raise ValidationError({"ordering": f"Expected one of: {', '.join(sorted(ORDERINGS))}."})
            queryset = queryset.order_by(ordering, "-id")
        return queryset
