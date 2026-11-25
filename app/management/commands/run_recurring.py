from django.core.management.base import BaseCommand

from app.services import recurring


class Command(BaseCommand):
    help = "Create the transactions of every recurring rule that is due"

    def handle(self, *args, **options):
        created = recurring.run_due()
        self.stdout.write(self.style.SUCCESS(f"{created} recurring transaction(s) created"))
