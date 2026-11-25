from django.core.management.base import BaseCommand

from app.models import SiteSetting


class Command(BaseCommand):
    help = "Switch maintenance mode on or off"

    def add_arguments(self, parser):
        parser.add_argument("state", choices=["on", "off"])
        parser.add_argument("--message", default="", help="Message shown to users while maintenance is on")

    def handle(self, *args, **options):
        setting = SiteSetting.load()
        setting.maintenance = options["state"] == "on"
        setting.maintenance_message = options["message"] if setting.maintenance else ""
        setting.save()
        self.stdout.write(self.style.SUCCESS(f"Maintenance is {options['state']}"))
