from django.db.models.signals import post_save, pre_delete
from .models import Transaction, Account
from django.dispatch import receiver

@receiver(post_save, sender=Transaction)
def updateBalance(sender, instance, **kwargs):
    account_sender = Account.objects.get(pk=instance.sender.pk)
    account_receiver = Account.objects.get(pk=instance.receiver.pk)

    account_sender.balance -= instance.amount
    account_receiver.balance += instance.amount

    account_sender.save()
    account_receiver.save()

@receiver(pre_delete, sender=Transaction)
def updateBalance(sender, instance, **kwargs):
    account_sender = Account.objects.get(pk=instance.sender.pk)
    account_receiver = Account.objects.get(pk=instance.receiver.pk)

    account_sender.balance += instance.amount
    account_receiver.balance -= instance.amount

    account_sender.save()
    account_receiver.save()