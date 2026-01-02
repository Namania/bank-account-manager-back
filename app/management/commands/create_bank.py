from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from app.models.account import Account
import datetime

class Command(BaseCommand):
    help = "Create Bank user & account"

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username="Bank")
            self.stdout.write(self.style.WARNING('Bank user already exists'))
        except User.DoesNotExist:
            user = User.objects.create(username="Bank", is_staff=False, is_active=True, date_joined=datetime.datetime.now())
            user.save()

            self.stdout.write(
                self.style.SUCCESS('Successfully creating "Bank" user')
            )

            try:
                Account.objects.get(owners=user, label="Bank")
                self.stdout.write(self.style.WARNING('Bank account already exists'))
            except Account.DoesNotExist:
                bank = Account.objects.create(owners=user, label="Bank", balance=0)
                bank.save()

                self.stdout.write(
                    self.style.SUCCESS('Successfully creating "Bank" account')
                )
