from django.db.models.signals import pre_delete
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from .models import Transaction, Account

@receiver(pre_delete, sender=Transaction)
def updateBalance(sender, instance: Transaction, **kwargs): # pylint: disable=unused-argument
    account_sender = Account.objects.get(pk=instance.sender.pk)
    account_receiver = Account.objects.get(pk=instance.receiver.pk)

    account_sender.balance += instance.amount * 100
    account_receiver.balance -= instance.amount * 100

    account_sender.save()
    account_receiver.save()

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs): # pylint: disable=unused-argument
    if created and not instance.username == "Bank":
        Token.objects.create(user=instance)

@receiver(post_save, sender=Transaction)
def update_account_balance(sender, instance: Transaction, created, **kwargs): # pylint: disable=unused-argument
    if created:
        receiver_account = instance.receiver
        sender_account = instance.sender

        if receiver_account.label != "Bank":
            receiver_account.balance += instance.amount * 100
            receiver_account.save()

        if sender_account.label != "Bank":
            sender_account.balance -= instance.amount * 100
            sender_account.save()

@receiver(post_save, sender=Account)
def first_transaction(sender, instance: Account, created, **kwargs): # pylint: disable=unused-argument
    if created:
        amount = instance.balance / 100
        instance.balance = 0
        instance.save()

        bank = Account.objects.filter(label="Bank").first()
        if not bank:
            return

        Transaction.objects.create(sender=bank, receiver=instance, amount=amount, comment="Création du compte")
