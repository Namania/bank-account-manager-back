from django.contrib.auth.models import User

from app.tests.base import ApiTestCase


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
