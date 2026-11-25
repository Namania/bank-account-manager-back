from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers

from app.auth import CsrfView, LoginView, LogoutView, RefreshView
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
    path('token/', LoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', RefreshView.as_view(), name='token_refresh'),
    path('token/logout/', LogoutView.as_view(), name='token_logout'),
    path('csrf/', CsrfView.as_view(), name='csrf'),
]

if settings.DEBUG:
    urlpatterns.append(path('auth/', include('rest_framework.urls', namespace='rest_framework')))
