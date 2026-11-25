from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework import routers

from app.auth import CsrfView, LoginView, LogoutView, RefreshView
from app.views import (
    AccountViewSet, BudgetViewSet, CategoryViewSet, HealthView, RecurringTransactionViewSet, StatsViewSet,
    TransactionViewSet, UserViewSet,
)

router = routers.DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'transactions', TransactionViewSet)
router.register(r'users', UserViewSet)
router.register(r'stats', StatsViewSet, basename='stats')
router.register(r'recurring-transactions', RecurringTransactionViewSet)
router.register(r'budgets', BudgetViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('admin/', admin.site.urls),
    path('token/', LoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', RefreshView.as_view(), name='token_refresh'),
    path('token/logout/', LogoutView.as_view(), name='token_logout'),
    path('csrf/', CsrfView.as_view(), name='csrf'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('health/', HealthView.as_view(), name='health'),
]

if settings.DEBUG:
    # Swagger UI loads its assets from a CDN, which the production CSP forbids.
    urlpatterns.append(path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'))
    urlpatterns.append(path('auth/', include('rest_framework.urls', namespace='rest_framework')))
