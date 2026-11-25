from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from app.models import Account


class BankFlagTests(TestCase):
    def test_only_one_bank_account(self):
        Account.objects.create(label="Bank", is_bank=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Account.objects.create(label="Autre", is_bank=True)

    def test_label_bank_does_not_make_a_bank(self):
        self.assertFalse(Account.objects.create(label="Bank").is_bank)

    def test_create_bank_command_is_idempotent(self):
        call_command("create_bank", verbosity=0)
        call_command("create_bank", verbosity=0)
        self.assertEqual(Account.objects.filter(is_bank=True).count(), 1)

    def test_create_bank_command_creates_no_user(self):
        call_command("create_bank", verbosity=0)
        self.assertFalse(User.objects.exists())
        self.assertEqual(Account.objects.get(is_bank=True).owners.count(), 0)
