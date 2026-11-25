from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from app.tests.base import PASSWORD, ApiTestCase


class UserApiTests(ApiTestCase):
    def test_cannot_promote_self_to_staff(self):
        response = self.as_user(self.mallory).patch(f"/users/{self.mallory.id}/", {"is_staff": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.mallory.refresh_from_db()
        self.assertFalse(self.mallory.is_staff)

    def test_non_staff_sees_only_self(self):
        response = self.as_user(self.mallory).get("/users/")
        self.assertEqual([user["id"] for user in response.data["results"]], [self.mallory.id])

    def test_cannot_read_other_user(self):
        self.assertEqual(self.as_user(self.mallory).get(f"/users/{self.alice.id}/").status_code, 404)

    def test_create_and_delete_are_disabled_even_for_staff(self):
        client = self.as_user(self.staff)
        self.assertEqual(client.post("/users/", {"username": "ghost"}, format="json").status_code, 405)
        self.assertEqual(client.delete(f"/users/{self.alice.id}/").status_code, 405)
        self.assertTrue(User.objects.filter(pk=self.alice.id).exists())

    def test_me_returns_current_user(self):
        response = self.as_user(self.alice).get("/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.alice.id)
        self.assertEqual(response.data["username"], "alice")

    def test_me_patch_updates_email_but_not_is_staff(self):
        response = self.as_user(self.alice).patch(
            "/users/me/", {"email": "a@example.org", "is_staff": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "a@example.org")
        self.assertFalse(self.alice.is_staff)


class PasswordChangeTests(ApiTestCase):
    NEW = "Nouveau-Mot2Passe!"

    def setUp(self):
        cache.clear()

    def change(self, client, current=PASSWORD, new=NEW):
        return client.post("/users/me/password/", {"current_password": current, "new_password": new}, format="json")

    def test_wrong_current_password_is_rejected(self):
        response = self.change(self.as_user(self.alice), current="nope")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.get(pk=self.alice.pk).check_password(PASSWORD))

    def test_weak_new_password_is_rejected(self):
        for weak in ["12345678", "alice", "short"]:
            with self.subTest(weak=weak):
                self.assertEqual(self.change(self.as_user(self.alice), new=weak).status_code, 400)

    def test_success_changes_password_and_keeps_this_session(self):
        client = APIClient()
        client.post("/token/", {"username": "alice", "password": PASSWORD}, format="json")
        old_refresh = client.cookies["refresh_token"].value
        response = self.change(client)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(User.objects.get(pk=self.alice.pk).check_password(self.NEW))
        self.assertEqual(client.get("/users/me/").status_code, 200)
        self.assertNotEqual(client.cookies["refresh_token"].value, old_refresh)

    def test_success_revokes_other_sessions(self):
        other_device = APIClient()
        other_device.post("/token/", {"username": "alice", "password": PASSWORD}, format="json")
        self.assertEqual(self.change(self.as_user(self.alice)).status_code, 204)
        self.assertEqual(other_device.post("/token/refresh/").status_code, 401)

    def test_attempts_are_throttled(self):
        client = self.as_user(self.alice)
        codes = [self.change(client, current="nope").status_code for _ in range(6)]
        self.assertEqual(codes, [400] * 5 + [429])
