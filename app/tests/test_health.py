from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.db import DatabaseError

from app.models import SiteSetting
from app.tests.base import ApiTestCase


class HealthTests(ApiTestCase):
    def set_maintenance(self, on, message=""):
        setting = SiteSetting.load()
        setting.maintenance, setting.maintenance_message = on, message
        setting.save()

    def test_health_is_public_and_reports_no_maintenance(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "maintenance": False, "message": ""})

    def test_maintenance_blocks_the_api_but_not_health_admin_or_login(self):
        self.set_maintenance(True, "Retour à 14 h")
        blocked = self.as_user(self.alice).get("/accounts/")
        self.assertEqual(blocked.status_code, 503)
        self.assertEqual(blocked.json(), {"detail": "The application is under maintenance.",
                                          "maintenance": True, "message": "Retour à 14 h"})
        self.assertEqual(self.client.get("/health/").json(),
                         {"status": "ok", "maintenance": True, "message": "Retour à 14 h"})
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)
        self.assertEqual(self.client.get("/csrf/").status_code, 200)
        self.assertEqual(self.client.post("/token/", {"username": "x", "password": "y"}, format="json").status_code, 401)

    def test_turning_maintenance_off_restores_the_api(self):
        self.set_maintenance(True)
        self.set_maintenance(False)
        self.assertEqual(self.as_user(self.alice).get("/accounts/").status_code, 200)

    def test_only_staff_can_toggle_through_the_endpoint(self):
        payload = {"maintenance": True, "message": "Mise à jour"}
        self.assertEqual(self.client.patch("/health/", payload, format="json").status_code, 401)
        self.assertEqual(self.as_user(self.alice).patch("/health/", payload, format="json").status_code, 403)
        self.assertFalse(SiteSetting.load().maintenance)
        response = self.as_user(self.staff).patch("/health/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "maintenance": True, "message": "Mise à jour"})
        self.assertEqual(self.as_user(self.alice).get("/transactions/").status_code, 503)

    def test_staff_can_turn_it_off_through_the_endpoint_while_it_is_on(self):
        self.set_maintenance(True)
        response = self.as_user(self.staff).patch("/health/", {"maintenance": False}, format="json")
        self.assertEqual(response.json()["maintenance"], False)

    def test_management_command_toggles(self):
        call_command("maintenance", "on", "--message", "Migration", stdout=StringIO())
        self.assertEqual((SiteSetting.load().maintenance, SiteSetting.load().maintenance_message), (True, "Migration"))
        call_command("maintenance", "off", stdout=StringIO())
        self.assertEqual((SiteSetting.load().maintenance, SiteSetting.load().maintenance_message), (False, ""))

    def test_health_is_503_when_the_database_is_down(self):
        with mock.patch("app.models.site.SiteSetting.load", side_effect=DatabaseError("down")):
            response = self.client.get("/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")

    def test_there_is_a_single_settings_row(self):
        SiteSetting.load()
        SiteSetting.load()
        self.assertEqual(SiteSetting.objects.count(), 1)
