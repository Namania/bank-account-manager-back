"""OpenAPI descriptions for the parts drf-spectacular cannot infer."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = 'app.authentication.CookieJWTAuthentication'
    name = 'cookieAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'cookie',
            'name': 'access_token',
            'description': 'HttpOnly cookie set by POST /token/. Writes also need the X-CSRFToken header.',
        }


CsrfTokenResponse = inline_serializer('CsrfToken', {'csrfToken': serializers.CharField()})
LoginRequest = inline_serializer('Login', {
    'username': serializers.CharField(),
    'password': serializers.CharField(),
})
