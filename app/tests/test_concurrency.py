import threading
import unittest

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TransactionTestCase

from app.models import Account, Transaction

WORKERS = 4
TRANSFERS_PER_WORKER = 15


@unittest.skipUnless(connection.vendor == "postgresql", "row locks need PostgreSQL (TEST_DATABASE=postgres)")
class ConcurrentLedgerTests(TransactionTestCase):
    def test_simultaneous_transactions_never_lose_an_update(self):
        bank = Account.objects.create(label="Bank", is_bank=True)
        owner = User.objects.create_user("alice", password="Pw-12345678!")
        account = Account.objects.create(label="Courant", balance=1_000_000)
        account.owners.set([owner])
        errors = []

        def spend():
            try:
                for _ in range(TRANSFERS_PER_WORKER):
                    Transaction.objects.create(sender=account, receiver=bank, amount=100)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                errors.append(exc)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=spend) for _ in range(WORKERS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        expected = 1_000_000 - WORKERS * TRANSFERS_PER_WORKER * 100
        self.assertEqual(Account.objects.get(pk=account.pk).balance, expected)
