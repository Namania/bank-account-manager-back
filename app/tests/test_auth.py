from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from app.tests.base import PASSWORD


class AuthTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttling counters live in the cache
        self.user = User.objects.create_user("alice", password=PASSWORD)

    def login(self, client=None, password=PASSWORD):
        client = client or self.client
        return client.post("/token/", {"username": "alice", "password": password}, format="json")

    def test_login_sets_httponly_cookies_and_hides_tokens(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        for name in ["access_token", "refresh_token"]:
            self.assertTrue(response.cookies[name]["httponly"], name)
            self.assertEqual(response.cookies[name]["samesite"], "Lax", name)
        self.assertEqual(response.cookies["refresh_token"]["path"], "/token/")
        self.assertEqual(set(response.data), {"csrfToken"})

    def test_cookie_authenticates_requests(self):
        self.login()
        response = self.client.get("/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "alice")

    def test_login_is_throttled_after_5_attempts_per_minute(self):
        codes = [self.login(password="bad").status_code for _ in range(6)]
        self.assertEqual(codes, [401] * 5 + [429])

    def test_write_without_csrf_header_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf_token = self.login(client).data["csrfToken"]
        payload = {"label": "Perso", "color": "#000000"}
        self.assertEqual(client.post("/categories/", payload, format="json").status_code, 403)
        accepted = client.post("/categories/", payload, format="json", HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(accepted.status_code, 201)

    def test_read_does_not_need_csrf_header(self):
        client = APIClient(enforce_csrf_checks=True)
        self.login(client)
        self.assertEqual(client.get("/accounts/").status_code, 200)

    def test_csrf_endpoint_returns_usable_token(self):
        client = APIClient(enforce_csrf_checks=True)
        self.login(client)
        csrf_token = client.get("/csrf/").data["csrfToken"]
        response = client.post("/categories/", {"label": "x", "color": "#000000"}, format="json",
                               HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(response.status_code, 201)

    def test_refresh_rotates_and_old_token_is_rejected(self):
        self.login()
        old_refresh = self.client.cookies["refresh_token"].value
        first = self.client.post("/token/refresh/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(set(first.data), {"csrfToken"})
        self.assertNotEqual(self.client.cookies["refresh_token"].value, old_refresh)
        self.client.cookies["refresh_token"] = old_refresh
        replay = self.client.post("/token/refresh/")
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.cookies["access_token"].value, "")

    def test_refresh_requires_csrf_header(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf_token = self.login(client).data["csrfToken"]
        self.assertEqual(client.post("/token/refresh/").status_code, 403)
        self.assertEqual(client.post("/token/refresh/", HTTP_X_CSRFTOKEN=csrf_token).status_code, 200)

    def test_logout_revokes_refresh_and_clears_cookies(self):
        self.login()
        old_refresh = self.client.cookies["refresh_token"].value
        response = self.client.post("/token/logout/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(response.cookies["refresh_token"].value, "")
        self.client.cookies["refresh_token"] = old_refresh
        self.assertEqual(self.client.post("/token/refresh/").status_code, 401)

    def test_refresh_without_cookie_is_401(self):
        self.assertEqual(self.client.post("/token/refresh/").status_code, 401)

    def test_failed_login_is_logged_without_password(self):
        with self.assertLogs("app.security", level="WARNING") as logs:
            self.login(password="s3cret-bad")
        self.assertIn("login failed username=alice", logs.output[0])
        self.assertNotIn("s3cret-bad", logs.output[0])

    def test_api_requires_authentication(self):
        for url in ["/accounts/", "/transactions/", "/categories/", "/users/", "/users/me/"]:
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_authorization_header_is_ignored(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.user)}")
        self.assertEqual(self.client.get("/users/me/").status_code, 401)

    def test_garbage_access_cookie_is_401(self):
        self.client.cookies["access_token"] = "not-a-jwt"
        self.assertEqual(self.client.get("/users/me/").status_code, 401)

    def test_throttle_cannot_be_bypassed_with_spoofed_forwarded_for(self):
        # Behind the reverse proxy, the last X-Forwarded-For entry is the real client.
        codes = [
            self.client.post("/token/", {"username": "alice", "password": "bad"}, format="json",
                             HTTP_X_FORWARDED_FOR=f"10.0.0.{attempt}, 203.0.113.9").status_code
            for attempt in range(6)
        ]
        self.assertEqual(codes, [401] * 5 + [429])

    def test_admin_login_is_throttled(self):
        credentials = {"username": "alice", "password": "bad"}
        codes = [self.client.post("/admin/login/", credentials).status_code for _ in range(6)]
        self.assertEqual(codes, [200] * 5 + [429])

    def test_admin_login_page_itself_is_not_throttled(self):
        codes = {self.client.get("/admin/login/").status_code for _ in range(8)}
        self.assertEqual(codes, {200})
