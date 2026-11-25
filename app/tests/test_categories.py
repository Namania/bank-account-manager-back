from app.models import Category
from app.tests.base import ApiTestCase


class CategoryApiTests(ApiTestCase):
    def test_non_staff_cannot_modify_or_delete_global_category(self):
        client = self.as_user(self.mallory)
        self.assertEqual(client.patch(f"/categories/{self.category.id}/", {"label": "x"}, format="json").status_code, 403)
        self.assertEqual(client.delete(f"/categories/{self.category.id}/").status_code, 403)
        self.assertTrue(Category.objects.filter(pk=self.category.id, label="Courses").exists())

    def test_created_category_belongs_to_creator(self):
        response = self.as_user(self.mallory).post("/categories/", {"label": "Perso", "color": "#000000"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Category.objects.get(pk=response.data["id"]).owner, self.mallory)
        self.assertEqual(response.data["owner"], self.mallory.id)

    def test_owner_field_cannot_be_forged(self):
        response = self.as_user(self.mallory).post(
            "/categories/", {"label": "Perso", "color": "#000000", "owner": self.alice.id}, format="json"
        )
        self.assertEqual(Category.objects.get(pk=response.data["id"]).owner, self.mallory)

    def test_staff_creates_global_category(self):
        response = self.as_user(self.staff).post("/categories/", {"label": "Global", "color": "#000000"}, format="json")
        self.assertIsNone(Category.objects.get(pk=response.data["id"]).owner)

    def test_private_category_is_hidden_from_others(self):
        private = Category.objects.create(label="Secret", owner=self.alice)
        client = self.as_user(self.mallory)
        ids = [category["id"] for category in client.get("/categories/").data["results"]]
        self.assertIn(self.category.id, ids)
        self.assertNotIn(private.id, ids)
        self.assertEqual(client.get(f"/categories/{private.id}/").status_code, 404)

    def test_owner_can_edit_and_delete_own_category(self):
        own = Category.objects.create(label="Perso", owner=self.alice)
        client = self.as_user(self.alice)
        self.assertEqual(client.patch(f"/categories/{own.id}/", {"label": "y"}, format="json").status_code, 200)
        self.assertEqual(client.delete(f"/categories/{own.id}/").status_code, 204)

    def test_staff_can_edit_global_category(self):
        response = self.as_user(self.staff).patch(f"/categories/{self.category.id}/", {"label": "z"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_transaction_cannot_use_foreign_private_category(self):
        private = Category.objects.create(label="Secret", owner=self.alice)
        response = self.as_user(self.mallory).post(
            "/transactions/",
            {"sender": self.mallory_acc.id, "receiver": self.bank.id, "amount": "1.00", "category": private.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.balance(self.mallory_acc), 0)
