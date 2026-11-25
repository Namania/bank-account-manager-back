import datetime
from io import StringIO

from django.core.management import call_command

from app.models import Budget, Category, RecurringTransaction, Transaction
from app.services import recurring
from app.tests.base import ApiTestCase

D = datetime.date


class RecurringScheduleTests(ApiTestCase):
    def rule(self, **overrides):
        data = {"owner": self.alice, "sender": self.alice_acc, "receiver": self.bank, "amount": 80000,
                "comment": "Loyer", "frequency": "monthly", "start_date": D(2026, 1, 31),
                "next_date": D(2026, 1, 31)}
        data.update(overrides)
        return RecurringTransaction.objects.create(**data)

    def test_monthly_dates_clamp_to_month_end_without_drifting(self):
        rule = self.rule()
        dates = [recurring.occurrence_date(rule, n) for n in range(4)]
        self.assertEqual(dates, [D(2026, 1, 31), D(2026, 2, 28), D(2026, 3, 31), D(2026, 4, 30)])

    def test_weekly_and_yearly_dates(self):
        weekly = self.rule(frequency="weekly", start_date=D(2026, 1, 1))
        self.assertEqual(recurring.occurrence_date(weekly, 2), D(2026, 1, 15))
        yearly = self.rule(frequency="yearly", start_date=D(2024, 2, 29))
        self.assertEqual(recurring.occurrence_date(yearly, 1), D(2025, 2, 28))

    def test_run_due_creates_every_missed_occurrence_once(self):
        rule = self.rule()
        self.assertEqual(recurring.run_due(today=D(2026, 3, 15)), 2)
        self.assertEqual(recurring.run_due(today=D(2026, 3, 15)), 0)
        generated = Transaction.objects.filter(recurring=rule).order_by("date")
        self.assertEqual([tx.date for tx in generated], [D(2026, 1, 31), D(2026, 2, 28)])
        self.assertEqual({tx.comment for tx in generated}, {"Loyer"})
        self.assertEqual(self.balance(self.alice_acc), 100000 - 160000)
        rule.refresh_from_db()
        self.assertEqual((rule.next_date, rule.occurrences), (D(2026, 3, 31), 2))

    def test_rule_stops_after_end_date(self):
        rule = self.rule(end_date=D(2026, 2, 28))
        self.assertEqual(recurring.run_due(today=D(2026, 12, 31)), 2)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
        self.assertIsNone(rule.next_date)

    def test_paused_rule_is_skipped(self):
        self.rule(is_active=False)
        self.assertEqual(recurring.run_due(today=D(2026, 12, 31)), 0)

    def test_rule_on_deactivated_account_is_paused_not_run(self):
        rule = self.rule()
        self.alice_acc.is_active = False
        self.alice_acc.save()
        with self.assertLogs("app.audit", level="WARNING"):
            self.assertEqual(recurring.run_due(today=D(2026, 12, 31)), 0)
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)

    def test_management_command_reports_count(self):
        self.rule(start_date=D(2020, 1, 1), next_date=D(2099, 1, 1))
        out = StringIO()
        call_command("run_recurring", stdout=out)
        self.assertIn("0", out.getvalue())


class RecurringApiTests(ApiTestCase):
    def payload(self, **overrides):
        today = datetime.date.today()
        data = {"sender": self.alice_acc.id, "receiver": self.bank.id, "amount": "800.00", "comment": "Loyer",
                "frequency": "monthly", "start_date": (today + datetime.timedelta(days=5)).isoformat()}
        data.update(overrides)
        return data

    def test_create_sets_owner_and_next_date(self):
        response = self.as_user(self.alice).post("/recurring-transactions/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["next_date"], response.data["start_date"])
        self.assertEqual(response.data["amount"], "800.00")
        self.assertEqual(RecurringTransaction.objects.get(pk=response.data["id"]).owner, self.alice)

    def test_rule_starting_today_generates_its_first_transaction_immediately(self):
        today = datetime.date.today().isoformat()
        response = self.as_user(self.alice).post("/recurring-transactions/", self.payload(start_date=today),
                                                 format="json")
        self.assertEqual(response.data["occurrences"], 1)
        self.assertEqual(self.balance(self.alice_acc), 20000)

    def test_cannot_use_foreign_account(self):
        response = self.as_user(self.mallory).post("/recurring-transactions/", self.payload(), format="json")
        self.assertEqual(response.status_code, 400)

    def test_validation(self):
        client = self.as_user(self.alice)
        old = (datetime.date.today() - datetime.timedelta(days=800)).isoformat()
        for bad in [{"amount": "0"}, {"frequency": "daily"}, {"receiver": self.alice_acc.id},
                    {"start_date": old}, {"end_date": "2000-01-01"}]:
            with self.subTest(bad=bad):
                self.assertEqual(client.post("/recurring-transactions/", self.payload(**bad), format="json").status_code, 400)

    def test_rules_are_private(self):
        rule_id = self.as_user(self.alice).post("/recurring-transactions/", self.payload(), format="json").data["id"]
        client = self.as_user(self.mallory)
        self.assertEqual(client.get("/recurring-transactions/").data, [])
        self.assertEqual(client.delete(f"/recurring-transactions/{rule_id}/").status_code, 404)

    def test_can_pause_and_edit_amount_but_not_schedule(self):
        client = self.as_user(self.alice)
        rule_id = client.post("/recurring-transactions/", self.payload(), format="json").data["id"]
        paused = client.patch(f"/recurring-transactions/{rule_id}/", {"is_active": False, "amount": "850.00"}, format="json")
        self.assertEqual((paused.status_code, paused.data["is_active"], paused.data["amount"]), (200, False, "850.00"))
        moved = client.patch(f"/recurring-transactions/{rule_id}/", {"frequency": "weekly"}, format="json")
        self.assertEqual(moved.status_code, 400)

    def test_generated_transaction_links_back_to_its_rule(self):
        today = datetime.date.today().isoformat()
        client = self.as_user(self.alice)
        rule_id = client.post("/recurring-transactions/", self.payload(start_date=today), format="json").data["id"]
        newest = client.get("/transactions/").data["results"][0]
        self.assertEqual(newest["recurring"], rule_id)


class BudgetApiTests(ApiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        make = Transaction.objects.create
        make(sender=cls.alice_acc, receiver=cls.bank, amount=4000, category=cls.category, date=D(2026, 2, 3))
        make(sender=cls.alice_acc, receiver=cls.bank, amount=2000, category=cls.category, date=D(2026, 2, 20))
        make(sender=cls.alice_acc, receiver=cls.bank, amount=9900, category=cls.category, date=D(2026, 3, 1))

    def create(self, user=None, **overrides):
        data = {"category": self.category.id, "amount": "150.00"}
        data.update(overrides)
        return self.as_user(user or self.alice).post("/budgets/", data, format="json")

    def test_budget_reports_spent_and_remaining_for_the_month(self):
        self.assertEqual(self.create().status_code, 201)
        rows = self.as_user(self.alice).get("/budgets/?month=2026-02").data
        self.assertEqual(len(rows), 1)
        self.assertEqual({k: rows[0][k] for k in ("month", "amount", "spent", "remaining")},
                         {"month": "2026-02", "amount": "150.00", "spent": "60.00", "remaining": "90.00"})

    def test_remaining_goes_negative_when_overspent(self):
        self.create(amount="50.00")
        row = self.as_user(self.alice).get("/budgets/?month=2026-03").data[0]
        self.assertEqual((row["spent"], row["remaining"]), ("99.00", "-49.00"))

    def test_month_defaults_to_the_current_one(self):
        self.create()
        row = self.as_user(self.alice).get("/budgets/").data[0]
        self.assertEqual(row["month"], datetime.date.today().strftime("%Y-%m"))
        self.assertEqual(row["spent"], "0.00")

    def test_one_budget_per_category(self):
        self.create()
        self.assertEqual(self.create().status_code, 400)
        self.assertEqual(Budget.objects.count(), 1)

    def test_validation(self):
        private = Category.objects.create(label="Secret", owner=self.mallory)
        self.assertEqual(self.create(amount="0").status_code, 400)
        self.assertEqual(self.create(category=private.id).status_code, 400)
        self.assertEqual(self.as_user(self.alice).get("/budgets/?month=2026-13").status_code, 400)

    def test_budgets_are_private(self):
        budget_id = self.create().data["id"]
        client = self.as_user(self.mallory)
        self.assertEqual(client.get("/budgets/").data, [])
        self.assertEqual(client.patch(f"/budgets/{budget_id}/", {"amount": "1.00"}, format="json").status_code, 404)

    def test_two_users_can_budget_the_same_shared_category(self):
        self.create()
        self.assertEqual(self.create(user=self.mallory).status_code, 201)
