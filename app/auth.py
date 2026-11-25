"""Token endpoints: login, refresh, logout, CSRF token.

Tokens travel in HttpOnly cookies and never appear in a response body, so page
scripts cannot read them. See app.authentication for how requests are checked.
"""
import logging

from django.conf import settings
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ObjectDoesNotExist
from django.dispatch import receiver
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from app.authentication import enforce_csrf

security_log = logging.getLogger("app.security")

# The refresh cookie is only sent to the token endpoints.
REFRESH_COOKIE_PATH = "/token/"


def _set_cookie(response, name, value, lifetime, path):
    response.set_cookie(
        name,
        value,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path=path,
    )


def set_auth_cookies(response, access, refresh):
    _set_cookie(response, settings.AUTH_COOKIE_ACCESS, access, settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"], "/")
    _set_cookie(response, settings.AUTH_COOKIE_REFRESH, refresh, settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
                REFRESH_COOKIE_PATH)


def clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH, path=REFRESH_COOKIE_PATH,
                           samesite=settings.AUTH_COOKIE_SAMESITE)


class _TokenView(APIView):
    """Token endpoints authenticate by themselves, from credentials or the refresh cookie."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        # Without this DRF turns authentication failures into 403.
        return 'Bearer realm="api"'


class LoginView(_TokenView):
    throttle_scope = "token"
    # JSON only: an HTML form on another site cannot send it, and a cross-site
    # script needs a CORS preflight that only the allowed origins pass. That
    # prevents logging a victim's browser into someone else's account.
    parser_classes = [JSONParser]

    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        response = Response({"csrfToken": get_token(request)})
        set_auth_cookies(response, serializer.validated_data["access"], serializer.validated_data["refresh"])
        return response


class RefreshView(_TokenView):
    throttle_scope = "token_refresh"

    def post(self, request):
        enforce_csrf(request)
        serializer = TokenRefreshSerializer(data={"refresh": request.COOKIES.get(settings.AUTH_COOKIE_REFRESH, "")})
        try:
            valid = serializer.is_valid()
        except (TokenError, AuthenticationFailed, ObjectDoesNotExist):
            # Bad, expired or revoked token; deactivated or deleted user.
            valid = False
        if not valid:
            response = Response({"detail": "Refresh token is missing, expired or revoked."},
                                status=status.HTTP_401_UNAUTHORIZED)
            clear_auth_cookies(response)
            return response
        response = Response({"csrfToken": get_token(request)})
        set_auth_cookies(response, serializer.validated_data["access"], serializer.validated_data["refresh"])
        return response


class LogoutView(_TokenView):
    throttle_scope = "token_refresh"

    def post(self, request):
        enforce_csrf(request)
        try:
            RefreshToken(request.COOKIES.get(settings.AUTH_COOKIE_REFRESH, "")).blacklist()
        except TokenError:
            pass  # already expired or revoked: nothing left to revoke
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response


class CsrfView(_TokenView):
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request=None, **kwargs):  # pylint: disable=unused-argument
    ip_address = request.META.get("REMOTE_ADDR") if request is not None else None
    security_log.warning("login failed username=%s ip=%s", credentials.get("username"), ip_address)
