from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from app.models import Account, Category

PASSWORD = "Pw-12345678!"


class ApiTestCase(APITestCase):
    """Shared fixture: a bank, two regular users with one account each, a staff user."""

    @classmethod
    def setUpTestData(cls):
        cls.bank = Account.objects.create(label="Bank", is_bank=True)
        cls.alice = User.objects.create_user("alice", password=PASSWORD)
        cls.mallory = User.objects.create_user("mallory", password=PASSWORD)
        cls.staff = User.objects.create_user("staff", password=PASSWORD, is_staff=True)
        cls.alice_acc = cls.make_account(cls.alice, "Alice courant", 100000)
        cls.mallory_acc = cls.make_account(cls.mallory, "Mallory courant", 0)
        cls.category = Category.objects.create(label="Courses")

    @staticmethod
    def make_account(owner, label, cents=0):
        account = Account.objects.create(label=label, balance=cents)
        account.owners.set([owner])
        return account

    @staticmethod
    def as_user(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    @staticmethod
    def balance(account):
        """Balance in cents, read back from the database."""
        return Account.objects.get(pk=account.pk).balance
