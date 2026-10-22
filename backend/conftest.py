"""Test bootstrap: tests always run against the dev-fallback profile with the demo AI provider."""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DEV_FALLBACK"] = "1"
os.environ["AI_PROVIDER"] = "demo"
os.environ["DATABASE_URL"] = "sqlite://:memory:"
os.environ.setdefault("DJANGO_DEBUG", "0")

import pytest  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.core.management import call_command  # noqa: E402


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_curriculum", verbosity=0)


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(scope="session")
def private_media_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("private_media")


@pytest.fixture(autouse=True)
def _private_media_tmp(settings, private_media_dir):
    """Uploaded files go to a session-wide temp dir, never into the repository."""
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {
            "BACKEND": "apps.core.storage.PrivateFileSystemStorage",
            "OPTIONS": {"location": str(private_media_dir)},
        },
    }
    yield
