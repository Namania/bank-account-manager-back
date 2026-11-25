from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase


class SmokeTests(TestCase):
    def test_user_creation_does_not_crash(self):
        user = User.objects.create_user("zoe", password="Pw-12345678!")
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_no_pending_migration(self):
        call_command("makemigrations", "app", check=True, dry_run=True, verbosity=0)
