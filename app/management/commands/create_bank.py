from django.core.management.base import BaseCommand

from app.models.account import Account


class Command(BaseCommand):
    help = "Create the bank account, the counterparty for external credits and debits"

    def handle(self, *args, **options):
        Account.objects.get_or_create(is_bank=True, defaults={"label": "Bank"})

        self.stdout.write(
            self.style.SUCCESS('Successfully creating "Bank" account')
        )
