from django.contrib.auth.models import User
from rest_framework import serializers

from app.models.account import Account
from app.serializers.fields import CentsField


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class AccountSerializer(serializers.ModelSerializer):
    balance = CentsField(required=False)
    owners_details = OwnerSerializer(source='owners', many=True, read_only=True)

    class Meta:
        model = Account
        fields = ['id', 'owners', 'owners_details', 'label', 'balance', 'created_at', 'is_active', 'is_bank']
        read_only_fields = ['owners', 'created_at', 'is_active', 'is_bank']

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
        fields = ['id', 'label', 'is_active', 'is_bank']


class ShareSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    username = serializers.CharField()


class ImportResultSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    created = serializers.IntegerField()
    skipped = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField())
