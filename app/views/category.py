from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from app.models.category import Category
from app.permissions import IsOwnerOrStaffOrReadOnly, visible_categories
from app.serializers.category import CategorySerializer


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
