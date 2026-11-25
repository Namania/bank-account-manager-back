from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.permissions import usable_accounts
from app.serializers.category import CategorySerializer
from app.serializers.account import AccountSummarySerializer
from app.serializers.fields import CentsField

class TransactionSerializer(serializers.ModelSerializer):
    category_details = CategorySerializer(source='category', read_only=True)
    receiver_details = AccountSummarySerializer(source='receiver', read_only=True)
    sender_details = AccountSummarySerializer(source='sender', read_only=True)

    amount = CentsField()
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    receiver = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    sender = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())

    class Meta:
        model = Transaction
        fields = [
            'id',
            'sender',
            'receiver',
            'amount',
            'comment', 
            'category',
            'create_at',
            'category_details',
            'receiver_details',
            'sender_details'
        ]

    def get_fields(self):
        fields = super().get_fields()
        accounts = usable_accounts(self.context['request'].user)
        fields['sender'].queryset = accounts
        fields['receiver'].queryset = accounts
        return fields

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("The amount must be greater than zero.")
        return value

    def validate(self, attrs):
        # On a partial update, fall back to the stored side.
        sender = attrs.get('sender', getattr(self.instance, 'sender', None))
        receiver = attrs.get('receiver', getattr(self.instance, 'receiver', None))
        if sender is not None and sender == receiver:
            raise serializers.ValidationError("Sender and receiver must be different accounts.")
        return attrs

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().order_by('id')
    serializer_class = TransactionSerializer

    def get_queryset(self):
        user = self.request.user
        return Transaction.objects.all().order_by('create_at').reverse() if user.is_staff else Transaction.objects.filter(Q(sender__owners=user) | Q(receiver__owners=user)).distinct().order_by('create_at').reverse()

    @action(detail=False, url_path=r'by_account/(?P<account_id>\d+)')
    def by_account(self, _, account_id=None):
        queryset = self.get_queryset().filter(
            Q(sender_id=account_id) | Q(receiver_id=account_id)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
