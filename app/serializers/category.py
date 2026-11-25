from rest_framework import serializers

from app.models.category import Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'label', 'color', 'owner']
        read_only_fields = ['owner']
