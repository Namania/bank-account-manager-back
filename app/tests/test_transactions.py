from app.tests.base import ApiTestCase


class TransactionApiTests(ApiTestCase):
    def post(self, user, **overrides):
        data = {"sender": self.alice_acc.id, "receiver": self.bank.id, "amount": "10.00", "category": self.category.id}
        data.update(overrides)
        return self.as_user(user).post("/transactions/", data, format="json")

    def assert_rejected(self, response):
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.balance(self.alice_acc), 100000)
        self.assertEqual(self.balance(self.mallory_acc), 0)

    def test_owner_can_debit_own_account(self):
        response = self.post(self.alice)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount"], "10.00")
        self.assertEqual(self.balance(self.alice_acc), 99000)

    def test_cannot_debit_foreign_account(self):
        self.assert_rejected(self.post(self.mallory, receiver=self.mallory_acc.id))

    def test_cannot_credit_foreign_account(self):
        self.assert_rejected(self.post(self.mallory, sender=self.bank.id, receiver=self.alice_acc.id))

    def test_invalid_amounts_are_rejected(self):
        for amount in ["-200.00", "0", "abc", "1.234"]:
            with self.subTest(amount=amount):
                self.assert_rejected(self.post(self.alice, amount=amount))

    def test_same_sender_and_receiver_is_rejected(self):
        self.assert_rejected(self.post(self.alice, receiver=self.alice_acc.id))

    def test_inactive_account_is_rejected(self):
        self.alice_acc.isActive = False
        self.alice_acc.save()
        self.assert_rejected(self.post(self.alice))

    def test_update_amount_adjusts_balance(self):
        tx_id = self.post(self.alice).data["id"]
        response = self.as_user(self.alice).patch(f"/transactions/{tx_id}/", {"amount": "25.00"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(self.alice_acc), 97500)

    def test_update_cannot_point_to_foreign_account(self):
        tx_id = self.post(self.alice).data["id"]
        response = self.as_user(self.alice).patch(
            f"/transactions/{tx_id}/", {"sender": self.mallory_acc.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.balance(self.mallory_acc), 0)
        self.assertEqual(self.balance(self.alice_acc), 99000)

    def test_update_cannot_make_sender_equal_receiver(self):
        tx_id = self.post(self.alice).data["id"]
        response = self.as_user(self.alice).patch(
            f"/transactions/{tx_id}/", {"receiver": self.alice_acc.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_comment_is_editable(self):
        tx_id = self.post(self.alice).data["id"]
        response = self.as_user(self.alice).patch(f"/transactions/{tx_id}/", {"comment": "courses"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["comment"], "courses")
        self.assertEqual(self.balance(self.alice_acc), 99000)

    def test_details_do_not_leak_balance_or_owners(self):
        details = self.post(self.alice).data["sender_details"]
        self.assertEqual(set(details), {"id", "label", "isActive", "is_bank"})

    def test_foreign_transaction_is_invisible(self):
        tx_id = self.post(self.alice).data["id"]
        client = self.as_user(self.mallory)
        self.assertEqual(client.get(f"/transactions/{tx_id}/").status_code, 404)
        self.assertEqual(client.delete(f"/transactions/{tx_id}/").status_code, 404)

    def test_delete_restores_balance(self):
        tx_id = self.post(self.alice).data["id"]
        self.assertEqual(self.as_user(self.alice).delete(f"/transactions/{tx_id}/").status_code, 204)
        self.assertEqual(self.balance(self.alice_acc), 100000)

    def test_by_account_rejects_non_numeric_id(self):
        self.assertEqual(self.as_user(self.alice).get("/transactions/by_account/abc/").status_code, 404)

    def test_by_account_lists_own_transactions(self):
        self.post(self.alice)
        response = self.as_user(self.alice).get(f"/transactions/by_account/{self.alice_acc.id}/")
        self.assertEqual(response.data["count"], 2)  # opening transaction + the new one

    def test_staff_can_use_any_account(self):
        self.assertEqual(self.post(self.staff, receiver=self.mallory_acc.id).status_code, 201)
