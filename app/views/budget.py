import calendar
import datetime

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from app.models import Account, Budget
from app.serializers.budget import BudgetSerializer
from app.services import stats

_MONTH = OpenApiParameter("month", OpenApiTypes.STR, description="Month to report on, as YYYY-MM. Defaults to the current month.")


@extend_schema_view(list=extend_schema(parameters=[_MONTH]), retrieve=extend_schema(parameters=[_MONTH]))
class BudgetViewSet(viewsets.ModelViewSet):
    """Monthly spending limits per category, with what is spent and left for a month."""
    queryset = Budget.objects.all()
    serializer_class = BudgetSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Budget.objects.none()
        return Budget.objects.filter(owner=self.request.user).select_related('category')

    def _month(self):
        raw = self.request.query_params.get('month')
        if not raw:
            return datetime.date.today().replace(day=1)
        try:
            return datetime.datetime.strptime(raw, "%Y-%m").date()
        except ValueError as exc:
            raise ValidationError({'month': "Expected a month as YYYY-MM."}) from exc

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return context
        first = self._month()
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        accounts = list(Account.objects.filter(owners=self.request.user, is_bank=False).values_list('pk', flat=True))
        context['month'] = first.strftime("%Y-%m")
        context['spent_by_category'] = stats.expense_by_category(accounts, first, last)
        return context

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
