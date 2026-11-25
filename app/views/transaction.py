from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from app.filters import TransactionFilterBackend
from app.models.transaction import Transaction
from app.permissions import usable_accounts
from app.serializers.transaction import TransactionSerializer


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    filter_backends = [TransactionFilterBackend]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Transaction.objects.none()
        user = self.request.user
        if user.is_staff:
            return Transaction.objects.all()
        return Transaction.objects.filter(Q(sender__owners=user) | Q(receiver__owners=user)).distinct()

    def _require_both_sides_usable(self, transaction):
        """Seeing a transaction is not enough to change it.

        Editing or deleting moves the balance of both accounts, so both stored
        sides must be accounts the caller may use. A side whose account was
        deleted is ignored.
        """
        user = self.request.user
        if user.is_staff:
            return
        usable_ids = set(usable_accounts(user).values_list('pk', flat=True))
        stored_ids = {transaction.sender_id, transaction.receiver_id} - {None}
        if not stored_ids <= usable_ids:
            raise PermissionDenied("This transaction involves an account you cannot use.")

    def perform_update(self, serializer):
        self._require_both_sides_usable(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._require_both_sides_usable(instance)
        instance.delete()

    @action(detail=False, url_path=r'by_account/(?P<account_id>\d+)')
    def by_account(self, _, account_id=None):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            Q(sender_id=account_id) | Q(receiver_id=account_id)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
