"""The only place where account balances are written.

All amounts are integer cents. The bank account is a pure counterparty: its
balance is never tracked. A side whose account was deleted is skipped.
"""
import logging

from django.db import transaction

from app.models import Account, Transaction

audit = logging.getLogger("app.audit")

OPENING_COMMENT = "Création du compte"


def _shift(account: Account | None, delta: int) -> None:
    """Add delta cents to an account balance, under a row lock."""
    if account is None or account.is_bank or delta == 0:
        return
    locked = Account.objects.select_for_update().get(pk=account.pk)
    locked.balance += delta
    locked.save(update_fields=["balance"])


def _move(tx: Transaction, amount: int) -> None:
    with transaction.atomic():
        _shift(tx.receiver, amount)
        _shift(tx.sender, -amount)


def _describe(tx: Transaction) -> str:
    return f"id={tx.pk} sender={tx.sender_id} receiver={tx.receiver_id} amount={tx.amount}"


def apply_transaction(tx: Transaction) -> None:
    """Credit the receiver and debit the sender."""
    _move(tx, tx.amount)
    audit.info("transaction applied %s", _describe(tx))


def revert_transaction(tx: Transaction) -> None:
    """Exact inverse of apply_transaction."""
    _move(tx, -tx.amount)
    audit.info("transaction reverted %s", _describe(tx))


def open_account(account: Account) -> None:
    """Turn the initial balance of a new account into its first transaction."""
    if account.is_bank:
        return
    bank = Account.objects.filter(is_bank=True).first()
    if bank is None:
        audit.warning("account opened without a bank account id=%s: no opening transaction", account.pk)
        return

    opening = account.balance
    with transaction.atomic():
        Account.objects.filter(pk=account.pk).update(balance=0)
        if opening >= 0:
            Transaction.objects.create(sender=bank, receiver=account, amount=opening, comment=OPENING_COMMENT,
                                       is_opening=True)
        else:
            Transaction.objects.create(sender=account, receiver=bank, amount=-opening, comment=OPENING_COMMENT,
                                       is_opening=True)
