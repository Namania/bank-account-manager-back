from django.db.models.signals import pre_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Transaction, Account

@receiver(pre_delete, sender=Transaction)
def updateBalance(sender, instance: Transaction, **kwargs): # pylint: disable=unused-argument
    account_sender = Account.objects.get(pk=instance.sender.pk)
    account_receiver = Account.objects.get(pk=instance.receiver.pk)

    account_sender.balance += instance.amount
    account_receiver.balance -= instance.amount

    account_sender.save()
    account_receiver.save()

@receiver(post_save, sender=Transaction)
def update_account_balance(sender, instance: Transaction, created, **kwargs): # pylint: disable=unused-argument
    if created:
        receiver_account = instance.receiver
        sender_account = instance.sender

        if not receiver_account.is_bank:
            receiver_account.balance += instance.amount
            receiver_account.save()

        if not sender_account.is_bank:
            sender_account.balance -= instance.amount
            sender_account.save()

@receiver(post_save, sender=Account)
def first_transaction(sender, instance: Account, created, **kwargs): # pylint: disable=unused-argument
    if created:
        amount = instance.balance
        instance.balance = 0
        instance.save()

        bank = Account.objects.filter(is_bank=True).first()
        if not bank:
            return

        Transaction.objects.create(sender=bank, receiver=instance, amount=amount, comment="Création du compte")
