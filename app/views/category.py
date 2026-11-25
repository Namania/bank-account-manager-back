from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from app.models.category import Category
from app.permissions import IsOwnerOrStaffOrReadOnly, visible_categories
from app.serializers.category import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaffOrReadOnly]
    pagination_class = None  # a short list, shown whole in pickers

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Category.objects.none()
        return visible_categories(self.request.user).order_by('id')

    def perform_create(self, serializer):
        # Staff create shared categories; everyone else creates private ones.
        user = self.request.user
        serializer.save(owner=None if user.is_staff else user)
