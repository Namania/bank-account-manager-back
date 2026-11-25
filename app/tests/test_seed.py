import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.db.models import Q, Sum
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from app.models import Account, Budget, Category, RecurringTransaction, Transaction


def seed(*args):
    out = StringIO()
    call_command("seed", *args, stdout=out)
    return out.getvalue()


@override_settings(DEBUG=True)
class SeedCommandTests(TestCase):
    def test_refuses_to_run_outside_debug(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            seed()
        self.assertFalse(Account.objects.exists())

    def test_creates_a_usable_dataset(self):
        output = seed()
        self.assertEqual(set(User.objects.values_list("username", flat=True)), {"alice", "bruno"})
        self.assertEqual(Account.objects.filter(is_bank=True).count(), 1)
        self.assertGreaterEqual(Account.objects.filter(is_bank=False).count(), 4)
        self.assertGreaterEqual(Transaction.objects.count(), 150)
        self.assertGreaterEqual(Category.objects.count(), 8)
        self.assertGreaterEqual(Budget.objects.count(), 3)
        self.assertIn("alice", output)

    def test_demo_users_can_sign_in_and_see_six_months_of_statistics(self):
        seed()
        client = APIClient()
        login = client.post("/token/", {"username": "alice", "password": "demo-password"}, format="json")
        self.assertEqual(login.status_code, 200)
        months = client.get("/stats/monthly/").data
        self.assertGreaterEqual(len(months), 6)
        self.assertTrue(all(float(month["balance"]) > 0 for month in months), months)
        self.assertTrue(all(float(month["expense"]) > 0 for month in months[1:-1]))

    def test_every_balance_matches_its_transactions(self):
        seed()
        for account in Account.objects.filter(is_bank=False):
            credit = Transaction.objects.filter(receiver=account).aggregate(s=Sum("amount", default=0))["s"]
            debit = Transaction.objects.filter(sender=account).aggregate(s=Sum("amount", default=0))["s"]
            self.assertEqual(account.balance, credit - debit, account.label)
            self.assertGreaterEqual(account.balance, 0, account.label)

    def test_data_is_plausible(self):
        seed()
        today = datetime.date.today()
        self.assertFalse(Transaction.objects.filter(Q(amount__lte=0, is_opening=False) | Q(date__gt=today)).exists())
        self.assertFalse(Transaction.objects.filter(is_opening=False, comment__isnull=True).exists())
        rules = RecurringTransaction.objects.all()
        self.assertGreaterEqual(rules.count(), 4)
        self.assertTrue(all(rule.is_active and rule.next_date > today for rule in rules))
        self.assertTrue(Transaction.objects.filter(recurring__isnull=False).exists())
        shared = Account.objects.get(label="Compte joint")
        self.assertEqual(shared.owners.count(), 2)

    def test_refuses_to_run_twice_without_reset(self):
        seed()
        with self.assertRaises(CommandError):
            seed()

    def test_reset_rebuilds_the_same_data_and_keeps_other_users(self):
        User.objects.create_superuser("admin", password="x")
        seed()
        first = (Transaction.objects.count(), sorted(Account.objects.values_list("label", "balance")))
        seed("--reset")
        second = (Transaction.objects.count(), sorted(Account.objects.values_list("label", "balance")))
        self.assertEqual(first, second)
        self.assertTrue(User.objects.filter(username="admin").exists())
        self.assertEqual(Account.objects.filter(is_bank=True).count(), 1)
