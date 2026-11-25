from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from app.models.account import Account
from app.serializers.account import AccountSerializer, AccountSummarySerializer


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def get_queryset(self):
        user = self.request.user
        return Account.objects.all().order_by('id') if user.is_staff else Account.objects.filter(owners=user, is_active=True).order_by('id')

    def _protect_bank(self, account):
        if account.is_bank and not self.request.user.is_staff:
            raise PermissionDenied("The bank account can only be managed by staff.")

    def perform_create(self, serializer):
        account = serializer.save()
        account.owners.set([self.request.user])

    def perform_update(self, serializer):
        self._protect_bank(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._protect_bank(instance)
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @action(detail=False)
    def bank(self, _):
        """The counterparty for external credits and debits, visible to every user."""
        return Response(AccountSummarySerializer(get_object_or_404(Account, is_bank=True)).data)
