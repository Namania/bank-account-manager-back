import datetime

from rest_framework import viewsets

from app.models import RecurringTransaction
from app.serializers.recurring import RecurringTransactionSerializer
from app.services import recurring


class RecurringTransactionViewSet(viewsets.ModelViewSet):
    """Rules that create a transaction every week, month or year."""
    queryset = RecurringTransaction.objects.all()
    serializer_class = RecurringTransactionSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return RecurringTransaction.objects.none()
        user = self.request.user
        rules = RecurringTransaction.objects.all()
        return rules if user.is_staff else rules.filter(owner=user)

    def perform_create(self, serializer):
        rule = serializer.save(owner=self.request.user, next_date=serializer.validated_data['start_date'])
        # A rule starting today or earlier shows its transactions right away,
        # without waiting for the scheduler.
        recurring.run_rule(rule.pk, datetime.date.today())
        rule.refresh_from_db()
