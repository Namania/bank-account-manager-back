"""Environment variable parsing and validation."""
import os

from django.core.exceptions import ImproperlyConfigured

_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
_MIN_SECRET_KEY_LENGTH = 50


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean flag; only 1/true/yes/on (any case) are true.

    An empty value counts as unset: `HTTPS_ONLY=` in a .env file must fall back
    to the default instead of silently switching a protection off.
    """
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    return raw.lower() in _TRUE_VALUES


def env_list(name: str) -> list[str]:
    """Read a comma-separated list, trimmed, without empty items."""
    return [item.strip() for item in os.getenv(name, '').split(',') if item.strip()]


def check_production_settings(secret_key: str, allowed_hosts: list[str]) -> None:
    """Refuse to start in production with a weak key or a wildcard host."""
    if secret_key.startswith('django-insecure-') or len(secret_key) < _MIN_SECRET_KEY_LENGTH:
        raise ImproperlyConfigured(
            f"SECRET_KEY must be a random value of at least {_MIN_SECRET_KEY_LENGTH} characters"
        )
    if '*' in allowed_hosts:
        raise ImproperlyConfigured("ALLOWED_HOSTS must not contain '*' when DEBUG is off")
