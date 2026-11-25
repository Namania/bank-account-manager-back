import datetime

from django.test import override_settings

from app.models import Category, Transaction
from app.tests.base import ApiTestCase


class ListShapeTests(ApiTestCase):
    def test_accounts_and_categories_are_plain_lists(self):
        client = self.as_user(self.alice)
        self.assertEqual([a["id"] for a in client.get("/accounts/").data], [self.alice_acc.id])
        self.assertEqual([c["id"] for c in client.get("/categories/").data], [self.category.id])

    def test_transactions_stay_paginated(self):
        self.assertIn("results", self.as_user(self.alice).get("/transactions/").data)


class FixtureMixin:
    """alice: 1000.00 opening on 'today', then a known set of dated operations."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.loisirs = Category.objects.create(label="Loisirs", color="#ff0000")
        cls.savings = cls.make_account(cls.alice, "Alice épargne")
        d = datetime.date
        make = Transaction.objects.create
        cls.t_food = make(sender=cls.alice_acc, receiver=cls.bank, amount=4000, category=cls.category,
                          comment="Marché du samedi", date=d(2026, 1, 10))
        cls.t_fun = make(sender=cls.alice_acc, receiver=cls.bank, amount=2500, category=cls.loisirs,
                         comment="Cinéma", date=d(2026, 1, 20))
        cls.t_salary = make(sender=cls.bank, receiver=cls.alice_acc, amount=200000, comment="Salaire",
                            date=d(2026, 2, 1))
        cls.t_food2 = make(sender=cls.alice_acc, receiver=cls.bank, amount=6000, category=cls.category,
                           comment="Supermarché", date=d(2026, 2, 15))
        cls.t_transfer = make(sender=cls.alice_acc, receiver=cls.savings, amount=50000, comment="Virement épargne",
                              date=d(2026, 2, 20))


class TransactionFilterTests(FixtureMixin, ApiTestCase):
    def ids(self, query):
        response = self.as_user(self.alice).get(f"/transactions/?{query}")
        self.assertEqual(response.status_code, 200, response.data)
        return [tx["id"] for tx in response.data["results"]]

    def test_date_range(self):
        self.assertEqual(self.ids("date_from=2026-01-15&date_to=2026-02-01"), [self.t_salary.id, self.t_fun.id])

    def test_category(self):
        self.assertEqual(self.ids(f"category={self.category.id}"), [self.t_food2.id, self.t_food.id])

    def test_uncategorized(self):
        self.assertEqual(self.ids("category=none&date_from=2026-02-01&date_to=2026-02-28"),
                         [self.t_transfer.id, self.t_salary.id])

    def test_account(self):
        self.assertEqual(self.ids(f"account={self.savings.id}&date_to=2026-02-28"), [self.t_transfer.id])

    def test_amount_range_is_in_euros(self):
        self.assertEqual(self.ids("amount_min=30.00&amount_max=60.00"), [self.t_food2.id, self.t_food.id])

    def test_search_in_comment(self):
        self.assertEqual(self.ids("search=march"), [self.t_food2.id, self.t_food.id])

    def test_ordering(self):
        self.assertEqual(self.ids("ordering=amount&date_to=2026-02-28")[:2], [self.t_fun.id, self.t_food.id])
        self.assertEqual(self.ids("ordering=-amount")[0], self.t_salary.id)

    def test_filters_combine(self):
        self.assertEqual(self.ids(f"category={self.category.id}&date_from=2026-02-01"), [self.t_food2.id])

    def test_invalid_values_are_400(self):
        client = self.as_user(self.alice)
        for query in ["date_from=hier", "amount_min=abc", "category=x", "account=x", "ordering=password"]:
            with self.subTest(query=query):
                self.assertEqual(client.get(f"/transactions/?{query}").status_code, 400)

    def test_filters_never_widen_access(self):
        response = self.as_user(self.mallory).get(f"/transactions/?account={self.alice_acc.id}")
        self.assertEqual(response.data["results"], [])

    def test_by_account_accepts_the_same_filters(self):
        response = self.as_user(self.alice).get(f"/transactions/by_account/{self.alice_acc.id}/?search=cin")
        self.assertEqual([tx["id"] for tx in response.data["results"]], [self.t_fun.id])


class StatsTests(FixtureMixin, ApiTestCase):
    def get(self, path, user=None):
        response = self.as_user(user or self.alice).get(path)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_by_category_sums_expenses_and_ignores_transfers_and_opening(self):
        rows = self.get("/stats/by_category/?date_to=2026-12-31&date_from=2026-01-01")
        self.assertEqual(rows, [
            {"category": self.category.id, "label": "Courses", "color": "#007bff",
             "expense": "100.00", "income": "0.00"},
            {"category": self.loisirs.id, "label": "Loisirs", "color": "#ff0000",
             "expense": "25.00", "income": "0.00"},
            {"category": None, "label": None, "color": None, "expense": "0.00", "income": "2000.00"},
        ])

    def test_by_category_date_range(self):
        rows = self.get("/stats/by_category/?date_from=2026-02-01&date_to=2026-02-28")
        self.assertEqual([(r["category"], r["expense"]) for r in rows],
                         [(self.category.id, "60.00"), (None, "0.00")])

    def test_by_category_for_one_account_counts_transfers_out(self):
        rows = self.get(f"/stats/by_category/?account={self.savings.id}&date_from=2026-01-01&date_to=2026-12-31")
        self.assertEqual(rows, [{"category": None, "label": None, "color": None,
                                 "expense": "0.00", "income": "500.00"}])

    def test_monthly_income_expense_net_and_end_balance(self):
        rows = self.get("/stats/monthly/?date_from=2026-01-01&date_to=2026-03-31")
        self.assertEqual(rows, [
            {"month": "2026-01", "income": "0.00", "expense": "65.00", "net": "-65.00", "balance": "-65.00"},
            {"month": "2026-02", "income": "2000.00", "expense": "60.00", "net": "1940.00", "balance": "1875.00"},
            {"month": "2026-03", "income": "0.00", "expense": "0.00", "net": "0.00", "balance": "1875.00"},
        ])

    def test_monthly_balance_matches_current_balance_in_the_last_month(self):
        rows = self.get("/stats/monthly/")
        total = self.balance(self.alice_acc) + self.balance(self.savings)
        self.assertEqual(rows[-1]["balance"], f"{total / 100:.2f}")
        self.assertEqual(rows[0]["month"], "2026-01")

    def test_stats_are_scoped_to_the_caller(self):
        self.assertEqual(self.get("/stats/by_category/", self.mallory), [])
        client = self.as_user(self.mallory)
        self.assertEqual(client.get(f"/stats/monthly/?account={self.alice_acc.id}").status_code, 404)

    def test_stats_reject_invalid_dates(self):
        self.assertEqual(self.as_user(self.alice).get("/stats/monthly/?date_from=nope").status_code, 400)


class SchemaTests(ApiTestCase):
    def test_schema_requires_authentication(self):
        self.assertEqual(self.client.get("/schema/").status_code, 401)

    def test_schema_describes_the_api(self):
        response = self.as_user(self.alice).get("/schema/?format=json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for path in ["/transactions/", "/accounts/bank/", "/users/me/password/", "/stats/monthly/", "/token/"]:
            self.assertIn(path, paths)

    @override_settings(DEBUG=False)
    def test_interactive_docs_are_not_exposed_outside_debug(self):
        self.assertEqual(self.as_user(self.alice).get("/docs/").status_code, 404)
