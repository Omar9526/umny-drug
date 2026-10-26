"""Web Push (RFC 8030 + VAPID) delivery of ``ParentNotification`` rows to subscribed devices.

Push is a best-effort side channel: the in-app notification list stays the source of truth. Without
VAPID keys (``manage.py vapid_keys``) everything here is a no-op and ``GET /parents/push/`` reports
``enabled: false`` so the client never offers the toggle.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from apps.accounts.models import ParentProfile
from apps.core.audit import audit

from .models import ParentNotification, PushSubscription

logger = logging.getLogger("umnydrug.push")

GONE_STATUSES = frozenset({404, 410})
# Rate limiting by the push service is not the device's fault; neither are 5xx and network errors.
TRANSIENT_STATUSES = frozenset({429})
MAX_CONSECUTIVE_FAILURES = 5
MAX_DEVICES_PER_PARENT = 10
BODY_LIMIT = 180
NOTIFICATIONS_PATH = "/parent/notifications"
REQUEST_TIMEOUT_S = 10
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Keys and endpoints
# ---------------------------------------------------------------------------
def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _public_bytes(vapid: Vapid) -> bytes:
    return vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)


def generate_keypair() -> tuple[str, str]:
    """New VAPID pair ``(private, public)``: raw 32-byte scalar and X9.62 uncompressed point, base64url.

    The public form is exactly what the browser expects as ``applicationServerKey``.
    """
    vapid = Vapid()
    vapid.generate_keys()
    private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    return b64url(private), b64url(_public_bytes(vapid))


def derive_public_key(private_key: str) -> str:
    """Public key that belongs to a base64url private key; ``ValueError`` when the key is malformed."""
    try:
        vapid = Vapid.from_string(private_key)
    except Exception as exc:  # py_vapid surfaces binascii/cryptography errors of several kinds
        raise ValueError("VAPID_PRIVATE_KEY is not a valid base64url EC P-256 key") from exc
    return b64url(_public_bytes(vapid))


def validate_keys(p256dh: str, auth: str) -> None:
    """Browser keys from ``PushSubscription.toJSON()``; ``ValueError`` when they could not encrypt anything.

    pywebpush raises assorted errors on bad keys at delivery time; rejecting them at registration keeps
    ``deliver`` boring.
    """
    try:
        point = b64url_decode(p256dh)
        secret = b64url_decode(auth)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Ключи подписки должны быть в base64url.") from exc
    if len(secret) != 16:
        raise ValueError("Ключ auth должен быть длиной 16 байт.")
    if len(point) != 65:
        raise ValueError("Ключ p256dh должен быть несжатой точкой P-256 (65 байт).")
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    except ValueError as exc:
        raise ValueError("Ключ p256dh не является точкой на кривой P-256.") from exc


def endpoint_allowed(endpoint: str) -> bool:
    """Only https URLs of known push services (``WEBPUSH_ALLOWED_HOSTS``).

    The backend POSTs to whatever endpoint a client registers, so anything else would be a blind SSRF
    and a way to tie up the worker with slow hosts.
    """
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or port not in (None, 443) or parts.username or parts.password:
        return False
    for pattern in settings.WEBPUSH_ALLOWED_HOSTS:
        pattern = pattern.lower()
        if pattern.startswith(".") and host.endswith(pattern):
            return True
        if host == pattern:
            return True
    return False


def hash_endpoint(endpoint: str) -> str:
    """SHA-256 hex of an endpoint: the client proves it holds one without putting the URL into access logs."""
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def is_endpoint_hash(value: str) -> bool:
    return bool(_HEX_SHA256.match(value or ""))


def is_enabled() -> bool:
    return bool(settings.WEBPUSH_VAPID_PRIVATE_KEY and settings.WEBPUSH_VAPID_PUBLIC_KEY)


def config_for(parent: ParentProfile, *, endpoint_hash: str | None = None) -> dict:
    """State for the settings toggle; ``subscribed`` — whether the hashed endpoint belongs to the parent."""
    enabled = is_enabled()
    devices = PushSubscription.objects.filter(parent=parent)
    subscribed = bool(endpoint_hash) and any(
        hmac.compare_digest(hash_endpoint(endpoint), endpoint_hash)
        for endpoint in devices.values_list("endpoint", flat=True)
    )
    return {
        "enabled": enabled,
        "public_key": settings.WEBPUSH_VAPID_PUBLIC_KEY if enabled else None,
        "devices": devices.count(),
        "subscribed": subscribed,
    }


# ---------------------------------------------------------------------------
# Device registration
# ---------------------------------------------------------------------------
def subscribe(
    parent: ParentProfile,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str = "",
    request=None,
) -> tuple[PushSubscription, bool]:
    """Register or refresh a device. Returns ``(subscription, changed)``.

    The owner re-sending the same endpoint only refreshes the keys (the app does that after the push
    service rotates a subscription). An endpoint that belonged to another parent — a shared phone — moves
    to the caller. Only those two changes are audited. A parent keeps at most ``MAX_DEVICES_PER_PARENT``
    devices; the least recently registered ones are dropped.
    """
    fields = {
        "parent": parent,
        "p256dh": p256dh,
        "auth": auth,
        "user_agent": user_agent[:200],
        "failures": 0,
    }
    with transaction.atomic():
        existing = PushSubscription.objects.filter(endpoint=endpoint).only("parent_id").first()
        changed = existing is None or existing.parent_id != parent.id
        subscription, _ = PushSubscription.objects.update_or_create(endpoint=endpoint, defaults=fields)
        stale = list(
            PushSubscription.objects.filter(parent=parent)
            .order_by("-updated_at", "-created_at")
            .values_list("pk", flat=True)[MAX_DEVICES_PER_PARENT:]
        )
        if stale:
            PushSubscription.objects.filter(pk__in=stale).delete()
    if changed:
        audit("parent.push_subscribed", actor=parent.user, target=parent, request=request)
    return subscription, changed


def unsubscribe(parent: ParentProfile, *, endpoint: str, request=None) -> int:
    deleted, _ = PushSubscription.objects.filter(parent=parent, endpoint=endpoint).delete()
    if deleted:
        audit("parent.push_unsubscribed", actor=parent.user, target=parent, request=request)
    return deleted


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
def payload_for(notification: ParentNotification) -> dict:
    body = notification.body.strip()
    if len(body) > BODY_LIMIT:
        body = body[: BODY_LIMIT - 1].rstrip() + "…"
    return {
        "title": notification.title,
        "body": body,
        "url": NOTIFICATIONS_PATH,
        # One banner per (kind, child): a newer push replaces the older one instead of stacking.
        "tag": f"ud-{notification.kind}-{notification.student_id or 'family'}",
        "notification_id": str(notification.id),
        "kind": notification.kind,
    }


def schedule(notification: ParentNotification) -> None:
    """Queue delivery once the surrounding transaction commits, so the worker can see the row.

    ``robust=True``: a broker outage is logged, it must not turn an already committed request into a 500.
    """
    if not is_enabled():
        return
    from .tasks import send_push  # tasks import this module; keep the cycle lazy

    notification_id = str(notification.id)
    transaction.on_commit(lambda: send_push.delay(notification_id), robust=True)


def deliver(notification: ParentNotification) -> dict[str, int]:
    """Send one notification to every device of its parent. Never raises: push is best effort."""
    counters = {"sent": 0, "gone": 0, "failed": 0}
    if not is_enabled():
        return counters
    data = json.dumps(payload_for(notification), ensure_ascii=False)
    devices = PushSubscription.objects.filter(parent_id=notification.parent_id, parent__user__is_active=True)
    for subscription in devices:
        try:
            webpush(
                subscription_info=subscription.subscription_info,
                data=data,
                vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.WEBPUSH_VAPID_SUBJECT},
                ttl=settings.WEBPUSH_TTL_SECONDS,
                timeout=REQUEST_TIMEOUT_S,
            )
        except WebPushException as exc:
            status = exc.status_code
            if status in GONE_STATUSES:
                subscription.delete()
                counters["gone"] += 1
                logger.info(
                    "Push subscription expired",
                    extra={"event": "push.gone", "subscription": str(subscription.id)},
                )
                continue
            counters["failed"] += 1
            permanent = status is not None and 400 <= status < 500 and status not in TRANSIENT_STATUSES
            _record_failure(subscription, status=status, count=permanent)
            continue
        except requests.RequestException as exc:
            # Network trouble on our side. The exception text holds the endpoint, so only its type is logged.
            counters["failed"] += 1
            logger.warning(
                "Push delivery network error (%s)",
                type(exc).__name__,
                extra={"event": "push.network_error", "subscription": str(subscription.id)},
            )
            continue
        except Exception:
            # A device with keys we cannot encrypt for must not stop the parent's other devices.
            counters["failed"] += 1
            logger.exception(
                "Push delivery failed unexpectedly",
                extra={"event": "push.error", "subscription": str(subscription.id)},
            )
            _record_failure(subscription, status=None, count=True)
            continue
        counters["sent"] += 1
        PushSubscription.objects.filter(pk=subscription.pk).update(failures=0, last_sent_at=timezone.now())
    return counters


def _record_failure(subscription: PushSubscription, *, status: int | None, count: bool) -> None:
    if not count:
        logger.warning(
            "Push delivery deferred",
            extra={"event": "push.deferred", "status": status, "subscription": str(subscription.id)},
        )
        return
    PushSubscription.objects.filter(pk=subscription.pk).update(failures=F("failures") + 1)
    subscription.refresh_from_db(fields=["failures"])
    logger.warning(
        "Push delivery failed",
        extra={
            "event": "push.failed",
            "status": status,
            "failures": subscription.failures,
            "subscription": str(subscription.id),
        },
    )
    if subscription.failures >= MAX_CONSECUTIVE_FAILURES:
        subscription.delete()
