from django.db import DatabaseError
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models.site import SiteSetting

_HealthResponse = inline_serializer('Health', {
    'status': serializers.ChoiceField(choices=['ok', 'error']),
    'maintenance': serializers.BooleanField(),
    'message': serializers.CharField(),
})


class MaintenanceSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    maintenance = serializers.BooleanField()
    message = serializers.CharField(max_length=200, allow_blank=True, required=False)


class HealthView(APIView):
    """Is the application up, and is it in maintenance? Staff can switch maintenance here."""

    def _is_read(self):
        # No request while the OpenAPI schema is being generated.
        return self.request is not None and self.request.method in SAFE_METHODS

    def get_authenticators(self):
        # Reading must work for everyone, even with an expired session cookie.
        return [] if self._is_read() else super().get_authenticators()

    def get_permissions(self):
        return [AllowAny()] if self._is_read() else [IsAdminUser()]

    @staticmethod
    def _payload(setting):
        return {'status': 'ok', 'maintenance': setting.maintenance, 'message': setting.maintenance_message}

    @extend_schema(responses={200: _HealthResponse, 503: _HealthResponse})
    def get(self, _request):
        try:
            return Response(self._payload(SiteSetting.load()))  # also proves the database answers
        except DatabaseError:
            return Response({'status': 'error', 'maintenance': False, 'message': ''},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @extend_schema(request=MaintenanceSerializer, responses=_HealthResponse)
    def patch(self, request):
        serializer = MaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        setting = SiteSetting.load()
        setting.maintenance = serializer.validated_data['maintenance']
        setting.maintenance_message = serializer.validated_data.get('message', '') if setting.maintenance else ''
        setting.save()
        return Response(self._payload(setting))
