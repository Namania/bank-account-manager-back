import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from bankAccountManager.env import env_bool, env_list, check_production_settings


class EnvTests(SimpleTestCase):
    def test_env_bool(self):
        cases = [("False", False), ("false", False), ("0", False), ("", False),
                 ("True", True), ("true", True), ("1", True), ("on", True)]
        for raw, expected in cases:
            with mock.patch.dict(os.environ, {"X_FLAG": raw}):
                self.assertIs(env_bool("X_FLAG"), expected, raw)

    def test_env_bool_default_when_unset(self):
        self.assertIs(env_bool("X_UNSET_FLAG", default=True), True)
        self.assertIs(env_bool("X_UNSET_FLAG"), False)

    def test_env_list_strips_and_drops_empty(self):
        with mock.patch.dict(os.environ, {"X_LIST": " a.fr , b.fr,, "}):
            self.assertEqual(env_list("X_LIST"), ["a.fr", "b.fr"])

    def test_production_rejects_weak_secret(self):
        for key in ["django-insecure-" + "a" * 50, "short"]:
            with self.assertRaises(ImproperlyConfigured):
                check_production_settings(key, ["a.fr"])

    def test_production_rejects_wildcard_host(self):
        with self.assertRaises(ImproperlyConfigured):
            check_production_settings("k" * 60, ["*"])

    def test_production_accepts_strong_config(self):
        check_production_settings("k" * 60, ["a.fr"])
