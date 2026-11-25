import datetime

from django.utils import timezone

from app.models import Account, Transaction
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
        self.alice_acc.is_active = False
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
        self.assertEqual(set(details), {"id", "label", "is_active", "is_bank"})

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


class TransactionWithForeignSideTests(ApiTestCase):
    """A transaction between two users (created by staff or through a shared account)."""

    def setUp(self):
        self.shared_tx = Transaction.objects.create(sender=self.alice_acc, receiver=self.mallory_acc, amount=100)

    def test_cannot_edit_amount_when_other_side_is_foreign(self):
        response = self.as_user(self.mallory).patch(
            f"/transactions/{self.shared_tx.id}/", {"amount": "5000.00"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.balance(self.alice_acc), 99900)
        self.assertEqual(self.balance(self.mallory_acc), 100)

    def test_cannot_delete_when_other_side_is_foreign(self):
        response = self.as_user(self.mallory).delete(f"/transactions/{self.shared_tx.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Transaction.objects.filter(pk=self.shared_tx.id).exists())
        self.assertEqual(self.balance(self.alice_acc), 99900)

    def test_can_still_read_it(self):
        self.assertEqual(self.as_user(self.mallory).get(f"/transactions/{self.shared_tx.id}/").status_code, 200)

    def test_staff_can_edit_it(self):
        response = self.as_user(self.staff).patch(
            f"/transactions/{self.shared_tx.id}/", {"amount": "2.00"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(self.mallory_acc), 200)

    def test_cannot_edit_transaction_of_deactivated_account(self):
        own = Transaction.objects.create(sender=self.alice_acc, receiver=self.bank, amount=1000)
        self.as_user(self.alice).delete(f"/accounts/{self.alice_acc.id}/")
        before = self.balance(self.alice_acc)
        response = self.as_user(self.alice).patch(f"/transactions/{own.id}/", {"amount": "500.00"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.balance(self.alice_acc), before)

    def test_transaction_with_deleted_side_stays_editable_and_deletable(self):
        tmp = Account.objects.create(label="tmp")
        orphan = Transaction.objects.create(sender=self.alice_acc, receiver=tmp, amount=1000)
        before = self.balance(self.alice_acc)
        tmp.delete()
        client = self.as_user(self.alice)
        self.assertEqual(client.patch(f"/transactions/{orphan.id}/", {"amount": "4.00"}, format="json").status_code, 200)
        self.assertEqual(self.balance(self.alice_acc), before + 600)
        self.assertEqual(client.delete(f"/transactions/{orphan.id}/").status_code, 204)
        self.assertEqual(self.balance(self.alice_acc), before + 1000)


class TransactionFieldTests(ApiTestCase):
    def post(self, **overrides):
        data = {"sender": self.alice_acc.id, "receiver": self.bank.id, "amount": "10.00"}
        data.update(overrides)
        return self.as_user(self.alice).post("/transactions/", data, format="json")

    def test_category_is_optional(self):
        self.assertEqual(self.post().status_code, 201)
        response = self.post(category=None)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["category"])

    def test_category_can_be_cleared(self):
        tx_id = self.post(category=self.category.id).data["id"]
        response = self.as_user(self.alice).patch(f"/transactions/{tx_id}/", {"category": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["category"])

    def test_date_defaults_to_today(self):
        self.assertEqual(self.post().data["date"], timezone.localdate().isoformat())

    def test_date_of_operation_can_be_set(self):
        response = self.post(date="2026-01-15")
        self.assertEqual(response.data["date"], "2026-01-15")
        self.assertEqual(Transaction.objects.get(pk=response.data["id"]).date, datetime.date(2026, 1, 15))

    def test_created_at_is_read_only(self):
        response = self.post(created_at="2001-01-01T00:00:00Z")
        self.assertFalse(response.data["created_at"].startswith("2001"))

    def test_list_is_ordered_by_operation_date_newest_first(self):
        self.post(date="2026-03-01", comment="mars")
        self.post(date="2026-05-01", comment="mai")
        self.post(date="2026-04-01", comment="avril")
        comments = [tx["comment"] for tx in self.as_user(self.alice).get("/transactions/").data["results"]]
        self.assertEqual([c for c in comments if c in ("mars", "avril", "mai")], ["mai", "avril", "mars"])

    def test_opening_transaction_is_flagged(self):
        rows = self.as_user(self.alice).get("/transactions/").data["results"]
        self.assertEqual([tx["is_opening"] for tx in rows], [True])
        self.assertFalse(self.post().data["is_opening"])
