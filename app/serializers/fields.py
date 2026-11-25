from rest_framework import serializers

from app.money import to_cents, to_euros


class CentsField(serializers.DecimalField):
    """API boundary for money: "10.50" on the wire, 1050 in the model."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        return to_cents(super().to_internal_value(data))

    def to_representation(self, value):
        return super().to_representation(to_euros(value))
