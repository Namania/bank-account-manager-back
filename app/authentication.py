"""Request authentication from the JWT access cookie.

Kept apart from the token views: DRF imports this module while it is still
loading its own settings, so it must not import rest_framework.views.

Because the browser sends cookies on its own, every write must also carry a
CSRF token in the X-CSRFToken header.
"""
from django.conf import settings
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


def enforce_csrf(request):
    """Same check as DRF's SessionAuthentication: safe methods pass, writes need the header."""
    check = CSRFCheck(lambda _request: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF Failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate from the access cookie. The Authorization header is not read."""

    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        enforce_csrf(request)
        return self.get_user(validated_token), validated_token
