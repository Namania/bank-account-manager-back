from app.models import Account, Transaction
from app.serializers.account import AccountSerializer
from app.tests.base import ApiTestCase


class AccountApiTests(ApiTestCase):
    def test_balance_is_ignored_on_update(self):
        response = self.as_user(self.mallory).patch(
            f"/accounts/{self.mallory_acc.id}/", {"balance": "999999.00"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(self.mallory_acc), 0)

    def test_owners_are_ignored_on_update(self):
        self.as_user(self.mallory).patch(
            f"/accounts/{self.mallory_acc.id}/", {"owners": [self.mallory.id, self.alice.id]}, format="json"
        )
        self.assertEqual(list(self.mallory_acc.owners.all()), [self.mallory])

    def test_creator_becomes_sole_owner(self):
        response = self.as_user(self.mallory).post(
            "/accounts/", {"label": "Épargne", "balance": "200.00", "owners": [self.alice.id]}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        account = Account.objects.get(pk=response.data["id"])
        self.assertEqual(list(account.owners.all()), [self.mallory])
        self.assertEqual(self.balance(account), 20000)
        self.assertEqual(response.data["balance"], "200.00")
        self.assertEqual(response.data["owners"], [self.mallory.id])

    def test_cannot_create_bank_account(self):
        self.bank.delete()
        response = self.as_user(self.mallory).post("/accounts/", {"label": "x", "is_bank": True}, format="json")
        self.assertFalse(Account.objects.get(pk=response.data["id"]).is_bank)

    def test_cannot_read_or_update_foreign_account(self):
        client = self.as_user(self.mallory)
        self.assertEqual(client.get(f"/accounts/{self.alice_acc.id}/").status_code, 404)
        self.assertEqual(client.patch(f"/accounts/{self.alice_acc.id}/", {"label": "x"}, format="json").status_code, 404)

    def test_delete_is_soft(self):
        self.assertEqual(self.as_user(self.alice).delete(f"/accounts/{self.alice_acc.id}/").status_code, 204)
        self.alice_acc.refresh_from_db()
        self.assertFalse(self.alice_acc.is_active)

    def test_non_staff_owner_cannot_modify_bank(self):
        self.bank.owners.add(self.mallory)
        client = self.as_user(self.mallory)
        self.assertEqual(client.patch(f"/accounts/{self.bank.id}/", {"label": "x"}, format="json").status_code, 403)
        self.assertEqual(client.delete(f"/accounts/{self.bank.id}/").status_code, 403)

    def test_rename_is_allowed(self):
        response = self.as_user(self.alice).patch(f"/accounts/{self.alice_acc.id}/", {"label": "Courant"}, format="json")
        self.assertEqual(response.data["label"], "Courant")
        self.assertEqual(response.data["balance"], "1000.00")

    def test_bank_endpoint_exposes_bank_summary_to_any_user(self):
        response = self.as_user(self.mallory).get("/accounts/bank/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"id": self.bank.id, "label": "Bank", "is_active": True, "is_bank": True})

    def test_bank_endpoint_is_404_without_bank(self):
        self.bank.delete()
        self.assertEqual(self.as_user(self.mallory).get("/accounts/bank/").status_code, 404)

    def test_rename_does_not_rewrite_balance_from_a_stale_copy(self):
        stale = Account.objects.get(pk=self.alice_acc.pk)
        Transaction.objects.create(sender=self.alice_acc, receiver=self.bank, amount=40000)
        serializer = AccountSerializer(stale, data={"label": "Renommé"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        renamed = serializer.save()
        self.assertEqual(self.balance(self.alice_acc), 60000)
        self.assertEqual(renamed.balance, 60000)
        self.assertEqual(Account.objects.get(pk=self.alice_acc.pk).label, "Renommé")

    def test_fields_use_snake_case(self):
        data = self.as_user(self.alice).get(f"/accounts/{self.alice_acc.id}/").data
        self.assertEqual(set(data), {"id", "owners", "label", "balance", "created_at", "is_active", "is_bank"})
