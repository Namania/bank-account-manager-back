from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from app.models.account import Account
from app.serializers.fields import CentsField


class AccountSerializer(serializers.ModelSerializer):
    balance = CentsField(required=False)

    class Meta:
        model = Account
        fields = ['id', 'owners', 'label', 'balance', 'create_at', 'isActive', 'is_bank']
        read_only_fields = ['owners', 'create_at', 'isActive', 'is_bank']

    def update(self, instance, validated_data):
        # The balance is only set at creation; afterwards it moves through
        # transactions (or the back-office).
        validated_data.pop('balance', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        # Write only what changed: saving the whole row would put back the
        # balance read at the start of the request and erase any transaction
        # committed in between.
        instance.save(update_fields=list(validated_data))
        instance.refresh_from_db(fields=['balance'])
        return instance


class AccountSummarySerializer(serializers.ModelSerializer):
    """What a counterparty may know about an account: never its balance or owners."""

    class Meta:
        model = Account
        fields = ['id', 'label', 'isActive', 'is_bank']


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def get_queryset(self):
        user = self.request.user
        return Account.objects.all().order_by('id') if user.is_staff else Account.objects.filter(owners=user, isActive=True).order_by('id')

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
        instance.isActive = False
        instance.save(update_fields=['isActive'])

    @action(detail=False)
    def bank(self, _):
        """The counterparty for external credits and debits, visible to every user."""
        return Response(AccountSummarySerializer(get_object_or_404(Account, is_bank=True)).data)
