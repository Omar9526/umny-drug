from django.apps import AppConfig


class ParentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.parents"
    verbose_name = "Родительский кабинет"

    def ready(self) -> None:
        from . import checks  # noqa: F401 — registers the VAPID configuration check
