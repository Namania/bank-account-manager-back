from rest_framework import serializers

from app.models import Budget, Category
from app.money import to_euros
from app.permissions import visible_categories
from app.serializers.category import CategorySerializer
from app.serializers.fields import CentsField


class BudgetSerializer(serializers.ModelSerializer):
    amount = CentsField()
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none())
    category_details = CategorySerializer(source='category', read_only=True)
    month = serializers.SerializerMethodField()
    spent = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = ['id', 'category', 'category_details', 'amount', 'month', 'spent', 'remaining']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request is not None and request.user.is_authenticated:
            fields['category'].queryset = visible_categories(request.user)
        return fields

    def _spent_cents(self, budget) -> int:
        return self.context.get('spent_by_category', {}).get(budget.category_id, 0)

    def get_month(self, _budget) -> str:
        return self.context.get('month', '')

    def get_spent(self, budget) -> str:
        return str(to_euros(self._spent_cents(budget)))

    def get_remaining(self, budget) -> str:
        return str(to_euros(budget.amount - self._spent_cents(budget)))

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("The budget must be greater than zero.")
        return value

    def validate_category(self, value):
        owner = self.context['request'].user
        existing = Budget.objects.filter(owner=owner, category=value)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("You already have a budget for this category.")
        return value
