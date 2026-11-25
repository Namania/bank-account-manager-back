from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from app.models.category import Category
from app.permissions import IsOwnerOrStaffOrReadOnly, visible_categories

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'label', 'color', 'owner']
        read_only_fields = ['owner']

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaffOrReadOnly]

    def get_queryset(self):
        return visible_categories(self.request.user).order_by('id')

    def perform_create(self, serializer):
        # Staff create shared categories; everyone else creates private ones.
        user = self.request.user
        serializer.save(owner=None if user.is_staff else user)
