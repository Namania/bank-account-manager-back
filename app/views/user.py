from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from app.auth import set_auth_cookies
from app.serializers.user import PasswordChangeSerializer, UserSerializer


class UserViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    """Read and edit profiles. Accounts are created and removed in the back-office only."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    throttle_scope = None

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        user = self.request.user
        return User.objects.all().order_by('id') if user.is_staff else User.objects.filter(id=user.id).order_by('id')

    def get_throttles(self):
        # Password guessing through this endpoint is limited like the login.
        self.throttle_scope = 'password' if self.action == 'password' else None
        return super().get_throttles()

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        if request.method == 'PATCH':
            serializer = self.get_serializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(responses={204: None})
    @action(detail=False, methods=['post'], url_path='me/password', serializer_class=PasswordChangeSerializer)
    def password(self, request):
        """Change the password, sign every other session out, keep this one."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)

        refresh = RefreshToken.for_user(user)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response
