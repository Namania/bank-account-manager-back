from app.models import Account, Transaction
from app.tests.base import ApiTestCase


class LedgerTests(ApiTestCase):
    @staticmethod
    def transfer(sender, receiver, cents):
        return Transaction.objects.create(sender=sender, receiver=receiver, amount=cents)

    def test_create_moves_balance(self):
        self.transfer(self.alice_acc, self.mallory_acc, 50000)
        self.assertEqual(self.balance(self.alice_acc), 50000)
        self.assertEqual(self.balance(self.mallory_acc), 50000)

    def test_delete_restores_both_balances(self):
        self.transfer(self.alice_acc, self.mallory_acc, 50000).delete()
        self.assertEqual(self.balance(self.alice_acc), 100000)
        self.assertEqual(self.balance(self.mallory_acc), 0)

    def test_update_amount_adjusts_balances(self):
        tx = self.transfer(self.alice_acc, self.mallory_acc, 50000)
        tx = Transaction.objects.get(pk=tx.pk)
        tx.amount = 20000
        tx.save()
        self.assertEqual(self.balance(self.alice_acc), 80000)
        self.assertEqual(self.balance(self.mallory_acc), 20000)

    def test_update_accounts_moves_effect(self):
        other = self.make_account(self.mallory, "Mallory épargne")
        tx = self.transfer(self.alice_acc, self.mallory_acc, 50000)
        tx = Transaction.objects.get(pk=tx.pk)
        tx.receiver = other
        tx.save()
        self.assertEqual(self.balance(self.mallory_acc), 0)
        self.assertEqual(self.balance(other), 50000)
        self.assertEqual(self.balance(self.alice_acc), 50000)

    def test_bank_balance_never_moves(self):
        tx = self.transfer(self.bank, self.mallory_acc, 1000)
        self.assertEqual(self.balance(self.bank), 0)
        self.assertEqual(self.balance(self.mallory_acc), 1000)
        tx.delete()
        self.assertEqual(self.balance(self.bank), 0)
        self.assertEqual(self.balance(self.mallory_acc), 0)

    def test_delete_with_deleted_account_reverts_remaining_side(self):
        tmp = Account.objects.create(label="tmp")
        tx = self.transfer(self.alice_acc, tmp, 10000)
        tmp.delete()
        Transaction.objects.get(pk=tx.pk).delete()
        self.assertEqual(self.balance(self.alice_acc), 100000)

    def test_update_with_deleted_account_does_not_crash(self):
        tmp = Account.objects.create(label="tmp")
        tx = self.transfer(self.alice_acc, tmp, 10000)
        tmp.delete()
        tx = Transaction.objects.get(pk=tx.pk)
        tx.amount = 4000
        tx.save()
        self.assertEqual(self.balance(self.alice_acc), 96000)

    def test_bank_account_gets_no_opening_transaction(self):
        self.assertFalse(Transaction.objects.filter(receiver=self.bank).exists())
        self.assertFalse(Transaction.objects.filter(sender=self.bank, receiver=self.bank).exists())

    def test_opening_balance_creates_bank_transaction(self):
        tx = Transaction.objects.get(receiver=self.alice_acc, sender=self.bank)
        self.assertEqual(tx.amount, 100000)
        self.assertEqual(self.balance(self.alice_acc), 100000)

    def test_negative_opening_balance(self):
        account = Account.objects.create(label="Découvert", balance=-5000)
        tx = Transaction.objects.get(sender=account, receiver=self.bank)
        self.assertEqual(tx.amount, 5000)
        self.assertEqual(self.balance(account), -5000)

    def test_opening_without_bank_keeps_balance(self):
        Transaction.objects.all().delete()
        self.bank.delete()
        with self.assertLogs("app.audit", level="WARNING"):
            account = Account.objects.create(label="Sans banque", balance=7000)
        self.assertEqual(self.balance(account), 7000)
        self.assertFalse(Transaction.objects.exists())

    def test_stale_instance_does_not_overwrite_balance(self):
        stale = Account.objects.get(pk=self.mallory_acc.pk)
        self.transfer(self.alice_acc, self.mallory_acc, 10000)
        self.transfer(self.alice_acc, stale, 10000)
        self.assertEqual(self.balance(self.mallory_acc), 20000)

    def test_apply_is_audited(self):
        with self.assertLogs("app.audit", level="INFO") as logs:
            self.transfer(self.alice_acc, self.mallory_acc, 100)
        self.assertIn("transaction applied", logs.output[0])
