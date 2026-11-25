from rest_framework import serializers

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.permissions import usable_accounts, visible_categories
from app.serializers.category import CategorySerializer
from app.serializers.account import AccountSummarySerializer
from app.serializers.fields import CentsField

class TransferSerializer(serializers.ModelSerializer):
    """Fields and rules shared by anything that moves money between two accounts."""
    category_details = CategorySerializer(source='category', read_only=True)
    receiver_details = AccountSummarySerializer(source='receiver', read_only=True)
    sender_details = AccountSummarySerializer(source='sender', read_only=True)

    amount = CentsField()
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none(), allow_null=True, required=False)
    receiver = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())
    sender = serializers.PrimaryKeyRelatedField(queryset=Account.objects.none())

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return fields  # schema generation: no caller to scope the choices to
        user = request.user
        accounts = usable_accounts(user)
        fields['category'].queryset = visible_categories(user)
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


class TransactionSerializer(TransferSerializer):

    class Meta:
        model = Transaction
        fields = [
            'id',
            'sender',
            'receiver',
            'amount',
            'comment',
            'category',
            'date',
            'created_at',
            'is_opening',
            'recurring',
            'category_details',
            'receiver_details',
            'sender_details'
        ]

        read_only_fields = ['created_at', 'is_opening', 'recurring']
