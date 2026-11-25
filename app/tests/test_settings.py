from django.conf import settings
from django.test import SimpleTestCase, TestCase

from bankAccountManager import settings_test as settings_module


class SettingsTests(SimpleTestCase):
    def test_debug_is_a_real_boolean(self):
        # The test runner forces settings.DEBUG, so check the module's own value.
        self.assertIs(settings_module.DEBUG, False)

    def test_use_tz_enabled(self):
        self.assertIs(settings.USE_TZ, True)

    def test_renderers_are_json_only(self):
        self.assertEqual(settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"],
                         ["rest_framework.renderers.JSONRenderer"])


class SurfaceTests(TestCase):
    def test_session_login_route_absent(self):
        self.assertEqual(self.client.get("/auth/login/").status_code, 404)

    def test_api_response_has_security_headers(self):
        response = self.client.get("/accounts/")
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none'; frame-ancestors 'none'")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("geolocation=()", response["Permissions-Policy"])

    def test_admin_has_no_api_csp(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Security-Policy", response)
