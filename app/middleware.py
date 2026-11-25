from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from rest_framework.throttling import SimpleRateThrottle

API_CSP = "default-src 'none'; frame-ancestors 'none'"
PERMISSIONS_POLICY = "geolocation=(), camera=(), microphone=()"
_CSP_EXEMPT_PREFIXES = ("/admin/", "/static/")


class SecurityHeadersMiddleware:
    """Headers Django does not set itself.

    The API only serves JSON, so it gets the strictest possible CSP. The admin
    and static files are left out (the admin needs its own scripts and styles),
    and so is DEBUG mode, where the browsable API is enabled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        if not settings.DEBUG and not request.path.startswith(_CSP_EXEMPT_PREFIXES):
            response.setdefault("Content-Security-Policy", API_CSP)
        return response


class _AdminLoginRateThrottle(SimpleRateThrottle):
    """Same budget as the API login (scope "token"), counted separately."""
    scope = "token"

    def get_cache_key(self, request, view):
        return f"throttle_admin_login_{self.get_ident(request)}"


class AdminLoginThrottleMiddleware:
    """Limit password attempts on the back-office login, the highest-value target."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path == reverse("admin:login"):
            if not _AdminLoginRateThrottle().allow_request(request, None):
                return HttpResponse("Too many login attempts. Try again in a minute.", status=429)
        return self.get_response(request)
