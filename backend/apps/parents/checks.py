"""Startup checks for Web Push configuration (``manage.py check``, ``runserver``, ``migrate``)."""

from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Tags, register

HINT = "Run `manage.py vapid_keys` and copy all three lines into .env (both keys must come from one run)."


@register(Tags.security)
def check_webpush_configuration(app_configs, **kwargs) -> list[Error]:
    from . import push

    private = settings.WEBPUSH_VAPID_PRIVATE_KEY
    public = settings.WEBPUSH_VAPID_PUBLIC_KEY
    subject = settings.WEBPUSH_VAPID_SUBJECT
    if not private and not public:
        return []
    if not (private and public):
        return [
            Error(
                "VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY must be set together.", hint=HINT, id="parents.E001"
            )
        ]
    try:
        derived = push.derive_public_key(private)
    except ValueError as exc:
        return [Error(str(exc), hint=HINT, id="parents.E002")]
    errors = []
    if derived != public:
        errors.append(
            Error("VAPID_PUBLIC_KEY does not belong to VAPID_PRIVATE_KEY.", hint=HINT, id="parents.E003")
        )
    if not subject.startswith(("mailto:", "https://")):
        errors.append(
            Error(
                "VAPID_SUBJECT must be a mailto: address or an https:// URL push services can contact.",
                id="parents.E004",
            )
        )
    return errors
