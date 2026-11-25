"""Thin triggers: every balance change is delegated to the ledger service."""
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import Account, Transaction
from .services import ledger

# pylint: disable=unused-argument

@receiver(pre_save, sender=Transaction)
def revert_previous_version(sender, instance: Transaction, **kwargs):
    """An edited transaction first undoes what its stored version did."""
    if instance.pk is None:
        return
    previous = Transaction.objects.filter(pk=instance.pk).first()
    if previous is not None:
        ledger.revert_transaction(previous)

@receiver(post_save, sender=Transaction)
def apply_saved_transaction(sender, instance: Transaction, **kwargs):
    ledger.apply_transaction(instance)

@receiver(pre_delete, sender=Transaction)
def revert_deleted_transaction(sender, instance: Transaction, **kwargs):
    ledger.revert_transaction(instance)

@receiver(post_save, sender=Account)
def open_new_account(sender, instance: Account, created, **kwargs):
    if created:
        ledger.open_account(instance)
