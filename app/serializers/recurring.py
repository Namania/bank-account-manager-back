import datetime

from rest_framework import serializers

from app.models import RecurringTransaction
from app.serializers.transaction import TransferSerializer
from app.services.recurring import MAX_BACKDATE_DAYS

_SCHEDULE_FIELDS = ('frequency', 'start_date')


class RecurringTransactionSerializer(TransferSerializer):
    class Meta:
        model = RecurringTransaction
        fields = [
            'id', 'sender', 'receiver', 'amount', 'comment', 'category',
            'frequency', 'start_date', 'end_date', 'next_date', 'occurrences', 'is_active',
            'category_details', 'receiver_details', 'sender_details',
        ]
        read_only_fields = ['next_date', 'occurrences']

    def validate_start_date(self, value):
        if value < datetime.date.today() - datetime.timedelta(days=MAX_BACKDATE_DAYS):
            raise serializers.ValidationError("The start date cannot be more than a year in the past.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None:
            for field in _SCHEDULE_FIELDS:
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError(
                        {field: "The schedule of an existing rule cannot change. Delete it and create a new one."}
                    )
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if end is not None and start is not None and end < start:
            raise serializers.ValidationError({'end_date': "The end date must not be before the start date."})
        return attrs
