from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from app.models.account import Account

class Command(BaseCommand):
    help = "Create Bank user & account"

    def handle(self, *args, **options):
        user, _ = User.objects.get_or_create(username="Bank", is_staff=False, is_active=True)
        self.stdout.write(
            self.style.SUCCESS('Successfully creating "Bank" user')
        )

        bank, _ = Account.objects.get_or_create(label="Bank", balance=0)
        bank.owners.set([user])
        bank.save()

        self.stdout.write(
            self.style.SUCCESS('Successfully creating "Bank" account')
        )
