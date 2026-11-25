from django.conf import settings

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
