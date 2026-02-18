from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from app.serializers.account import AccountViewSet
from app.serializers.category import CategoryViewSet
from app.serializers.transaction import TransactionViewSet
from app.serializers.user import UserViewSet

router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('admin/', admin.site.urls),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
