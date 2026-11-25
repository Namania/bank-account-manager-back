from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from app.admin.forms import AccountAdminForm
from app.money import to_cents, to_euros
from app.serializers.fields import CentsField
from app.tests.base import ApiTestCase


class MoneyTests(SimpleTestCase):
    def test_to_cents(self):
        self.assertEqual(to_cents(Decimal("10.50")), 1050)
        self.assertEqual(to_cents(Decimal("0.01")), 1)
        self.assertEqual(to_cents(Decimal("-3")), -300)
        self.assertIsInstance(to_cents(Decimal("10.50")), int)

    def test_to_cents_rejects_sub_cent_precision(self):
        with self.assertRaises(ValueError):
            to_cents(Decimal("1.234"))

    def test_to_euros(self):
        self.assertEqual(to_euros(1050), Decimal("10.50"))
        self.assertEqual(str(to_euros(5)), "0.05")
        self.assertEqual(str(to_euros(100000)), "1000.00")

    def test_cents_field_round_trip(self):
        field = CentsField()
        self.assertEqual(field.to_internal_value("10.50"), 1050)
        self.assertEqual(field.to_representation(1050), "10.50")

    def test_cents_field_rejects_malformed_input(self):
        for raw in ["1.234", "abc", ""]:
            with self.assertRaises(ValidationError, msg=raw):
                CentsField().to_internal_value(raw)


class MoneyApiTests(ApiTestCase):
    def test_account_api_speaks_euros(self):
        response = self.as_user(self.alice).get(f"/accounts/{self.alice_acc.id}/")
        self.assertEqual(response.data["balance"], "1000.00")
        self.assertEqual(self.balance(self.alice_acc), 100000)

    def test_back_office_shows_balance_in_euros(self):
        form = AccountAdminForm(instance=self.alice_acc)
        self.assertEqual(str(form["balance"].value()), "1000.00")

    def test_back_office_saves_balance_in_cents(self):
        data = {"label": "Alice", "balance": "10.50", "create_at": "2026-01-01 10:00:00", "isActive": "on"}
        form = AccountAdminForm(data, instance=self.alice_acc)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(self.balance(self.alice_acc), 1050)
