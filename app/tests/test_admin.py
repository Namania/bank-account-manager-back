from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from app.models import Account, Category, Transaction
from app.tests.base import ApiTestCase


class BackOfficeThemeTests(ApiTestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("root", password="Pw-12345678!")
        self.client.force_login(self.superuser)

    def test_unfold_replaces_jazzmin(self):
        self.assertIn("unfold", settings.INSTALLED_APPS)
        self.assertNotIn("jazzmin", settings.INSTALLED_APPS)
        self.assertLess(settings.INSTALLED_APPS.index("unfold"),
                        settings.INSTALLED_APPS.index("django.contrib.admin"))

    def test_every_registered_model_uses_the_unfold_admin(self):
        for model in [Account, Category, Transaction, User, Group]:
            self.assertIsInstance(admin.site._registry[model], UnfoldModelAdmin, model.__name__)  # pylint: disable=protected-access

    def test_pages_render_with_the_unfold_layout(self):
        urls = [
            "/admin/",
            "/admin/app/account/", "/admin/app/account/add/", f"/admin/app/account/{self.alice_acc.id}/change/",
            "/admin/app/transaction/", "/admin/app/transaction/add/",
            "/admin/app/category/", "/admin/app/category/add/",
            "/admin/auth/user/", "/admin/auth/user/add/", f"/admin/auth/user/{self.alice.id}/change/",
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "unfold/layouts/skeleton.html")

    def test_login_page_renders(self):
        self.client.logout()
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bank Account Manager")

    def test_balance_is_still_edited_in_euros(self):
        response = self.client.get(f"/admin/app/account/{self.alice_acc.id}/change/")
        self.assertContains(response, 'value="1000.00"')
