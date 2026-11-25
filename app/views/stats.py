from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.filters import parse_date, parse_int
from app.models import Account
from app.services import stats

_PARAMETERS = [
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="First day, inclusive."),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Last day, inclusive."),
    OpenApiParameter("account", OpenApiTypes.INT, description="Limit to one of your accounts."),
]


class StatsViewSet(viewsets.ViewSet):
    """Figures over the caller's own accounts, or one of them with `account`."""

    def _scope(self, request):
        owned = Account.objects.filter(owners=request.user, is_bank=False)
        account = parse_int(request.query_params, "account")
        if account is not None:
            return [get_object_or_404(owned, pk=account).pk]
        return list(owned.values_list("pk", flat=True))

    @staticmethod
    def _dates(request):
        return parse_date(request.query_params, "date_from"), parse_date(request.query_params, "date_to")

    @extend_schema(parameters=_PARAMETERS, responses=OpenApiTypes.OBJECT)
    @action(detail=False)
    def by_category(self, request):
        """Expense and income per category, largest expense first."""
        return Response(stats.by_category(self._scope(request), *self._dates(request)))

    @extend_schema(parameters=_PARAMETERS, responses=OpenApiTypes.OBJECT)
    @action(detail=False)
    def monthly(self, request):
        """Income, expense, net and end-of-month balance for each month, oldest first."""
        return Response(stats.monthly(self._scope(request), *self._dates(request)))
