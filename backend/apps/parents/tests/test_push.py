"""Web Push: device registration API, delivery and pruning, scheduling on notification creation, VAPID tooling."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.core.management import call_command
from django.test import TestCase
from pywebpush import WebPushException, webpush

from apps.accounts.models import ParentProfile, StudentProfile
from apps.accounts.services import _notify_parents_about_lockout, revoke_user_sessions
from apps.accounts.tests.helpers import make_family
from apps.core.models import AuditLog
from apps.parents import checks, push, services
from apps.parents.models import ParentNotification, PushSubscription

pytestmark = pytest.mark.django_db

PRIVATE, PUBLIC = push.generate_keypair()
SUBJECT = "mailto:ops@example.kg"
ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"
CONFIG_URL = "/api/v1/parents/push/"
SUBSCRIPTIONS_URL = "/api/v1/parents/push/subscriptions/"


@pytest.fixture
def vapid(settings):
    settings.WEBPUSH_VAPID_PRIVATE_KEY = PRIVATE
    settings.WEBPUSH_VAPID_PUBLIC_KEY = PUBLIC
    settings.WEBPUSH_VAPID_SUBJECT = SUBJECT


class FakeResponse:
    def __init__(self, status: int):
        self.status_code = status
        self.reason = ""
        self.text = ""
        self.headers: dict[str, str] = {}


def _client_keys() -> dict[str, str]:
    """A real browser-side key pair: pywebpush must be able to encrypt for it."""
    key = ec.generate_private_key(ec.SECP256R1())
    point = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return {"p256dh": push.b64url(point), "auth": push.b64url(b"0123456789abcdef")}


def _subscribe(client, endpoint: str = ENDPOINT):
    return client.post(SUBSCRIPTIONS_URL, {"endpoint": endpoint, "keys": _client_keys()}, format="json")


def _parent(email: str = "parent@example.com") -> ParentProfile:
    return ParentProfile.objects.get(user__email=email)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_config_reports_disabled_without_keys():
    fam = make_family()
    response = fam["parent"].get(CONFIG_URL)
    assert response.status_code == 200, response.content
    assert response.json() == {"enabled": False, "public_key": None, "devices": 0, "subscribed": False}
    refused = _subscribe(fam["parent"])
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "push_disabled"


def test_subscribe_is_idempotent_and_audited_once(vapid):
    fam = make_family()
    first = _subscribe(fam["parent"])
    assert first.status_code == 201, first.content
    assert first.json() == {"enabled": True, "public_key": PUBLIC, "devices": 1, "subscribed": True}

    again = _subscribe(fam["parent"])
    assert again.status_code == 200
    assert again.json()["devices"] == 1
    assert PushSubscription.objects.count() == 1
    assert AuditLog.objects.filter(action="parent.push_subscribed").count() == 1

    subscription = PushSubscription.objects.get()
    assert subscription.parent == _parent()
    assert subscription.subscription_info["endpoint"] == ENDPOINT


def test_config_tells_whether_this_endpoint_is_mine(vapid):
    fam1 = make_family(email="one@example.com")
    fam2 = make_family(email="two@example.com")
    assert _subscribe(fam1["parent"]).status_code == 201

    mine = fam1["parent"].get(CONFIG_URL, {"endpoint_hash": push.hash_endpoint(ENDPOINT)}).json()
    assert (mine["subscribed"], mine["devices"]) == (True, 1)
    theirs = fam2["parent"].get(CONFIG_URL, {"endpoint_hash": push.hash_endpoint(ENDPOINT)}).json()
    assert fam1["parent"].get(CONFIG_URL, {"endpoint_hash": "not-a-hash"}).json()["subscribed"] is False
    assert (theirs["subscribed"], theirs["devices"]) == (False, 0)
    assert fam1["parent"].get(CONFIG_URL).json()["subscribed"] is False


def test_subscribe_rejects_bad_payloads_and_students(vapid):
    fam = make_family()
    for endpoint in (
        "http://fcm.googleapis.com/fcm/send/x",
        "https://attacker.example/fcm/send/x",
        "https://fcm.googleapis.com:8443/fcm/send/x",
        "https://user:pw@fcm.googleapis.com/fcm/send/x",
        "https://notfcm.googleapis.com/fcm/send/x",
    ):
        bad = fam["parent"].post(
            SUBSCRIPTIONS_URL, {"endpoint": endpoint, "keys": _client_keys()}, format="json"
        )
        assert bad.status_code == 400, endpoint
    assert push.endpoint_allowed("https://updates.push.services.mozilla.com/wpush/v2/abc")
    assert push.endpoint_allowed("https://web.push.apple.com/QAbc")
    off_curve = {"p256dh": push.b64url(b"\x04" + b"\x00" * 64), "auth": push.b64url(b"0123456789abcdef")}
    assert (
        fam["parent"]
        .post(SUBSCRIPTIONS_URL, {"endpoint": ENDPOINT, "keys": off_curve}, format="json")
        .status_code
        == 400
    )
    short_auth = {**_client_keys(), "auth": push.b64url(b"short")}
    assert (
        fam["parent"]
        .post(SUBSCRIPTIONS_URL, {"endpoint": ENDPOINT, "keys": short_auth}, format="json")
        .status_code
        == 400
    )
    bad_keys = fam["parent"].post(
        SUBSCRIPTIONS_URL,
        {"endpoint": ENDPOINT, "keys": {"p256dh": "not base64!", "auth": "a"}},
        format="json",
    )
    assert bad_keys.status_code == 400
    assert _subscribe(fam["student"]).status_code == 403
    assert PushSubscription.objects.count() == 0


def test_shared_device_moves_to_the_parent_who_subscribed_last(vapid):
    fam1 = make_family(email="one@example.com")
    fam2 = make_family(email="two@example.com")
    assert _subscribe(fam1["parent"]).status_code == 201
    assert _subscribe(fam2["parent"]).status_code == 201
    assert PushSubscription.objects.get().parent == _parent("two@example.com")
    assert AuditLog.objects.filter(action="parent.push_subscribed").count() == 2

    # The previous owner cannot remove what is no longer theirs; the current owner can.
    assert fam1["parent"].delete(SUBSCRIPTIONS_URL, {"endpoint": ENDPOINT}, format="json").json() == {
        "deleted": 0
    }
    assert PushSubscription.objects.count() == 1
    assert fam2["parent"].delete(SUBSCRIPTIONS_URL, {"endpoint": ENDPOINT}, format="json").json() == {
        "deleted": 1
    }
    assert PushSubscription.objects.count() == 0
    assert AuditLog.objects.filter(action="parent.push_unsubscribed").count() == 1


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
def test_deliver_sends_prunes_gone_devices_and_counts_failures(vapid, monkeypatch):
    fam = make_family()
    for suffix in ("", "-gone", "-flaky", "-busy"):
        assert _subscribe(fam["parent"], ENDPOINT + suffix).status_code == 201
    calls: list[tuple[str, dict, dict]] = []

    def fake_webpush(subscription_info, data, **kwargs):
        calls.append((subscription_info["endpoint"], json.loads(data), kwargs))
        if subscription_info["endpoint"].endswith("-gone"):
            raise WebPushException("gone", response=FakeResponse(410))
        if subscription_info["endpoint"].endswith("-flaky"):
            raise WebPushException("bad request", response=FakeResponse(400))
        if subscription_info["endpoint"].endswith("-busy"):
            raise WebPushException("rate limited", response=FakeResponse(429))
        return FakeResponse(201)

    monkeypatch.setattr(push, "webpush", fake_webpush)
    notification = ParentNotification.objects.create(
        parent=_parent(), kind=ParentNotification.Kind.SYSTEM, title="Тест", body="x" * 400
    )

    assert push.deliver(notification) == {"sent": 1, "gone": 1, "failed": 2}
    assert {endpoint for endpoint, _, _ in calls} == {ENDPOINT + s for s in ("", "-gone", "-flaky", "-busy")}
    payload, kwargs = calls[0][1], calls[0][2]
    assert payload["title"] == "Тест"
    assert payload["url"] == "/parent/notifications"
    assert payload["notification_id"] == str(notification.id)
    assert len(payload["body"]) <= push.BODY_LIMIT and payload["body"].endswith("…")
    assert kwargs["vapid_private_key"] == PRIVATE
    assert kwargs["vapid_claims"] == {"sub": SUBJECT}
    assert kwargs["ttl"] == 24 * 60 * 60

    remaining = {s.endpoint: s.failures for s in PushSubscription.objects.all()}
    # 400 counts towards removal, 429 is the push service asking us to slow down
    assert remaining == {ENDPOINT: 0, ENDPOINT + "-flaky": 1, ENDPOINT + "-busy": 0}
    assert PushSubscription.objects.get(endpoint=ENDPOINT).last_sent_at is not None


def test_repeated_failures_drop_the_device(vapid, monkeypatch):
    fam = make_family()
    assert _subscribe(fam["parent"]).status_code == 201

    def always_failing(subscription_info, data, **kwargs):
        raise WebPushException("boom", response=FakeResponse(400))

    monkeypatch.setattr(push, "webpush", always_failing)
    notification = ParentNotification.objects.create(
        parent=_parent(), kind=ParentNotification.Kind.SYSTEM, title="Тест", body=""
    )
    for _ in range(push.MAX_CONSECUTIVE_FAILURES - 1):
        push.deliver(notification)
    assert PushSubscription.objects.get().failures == push.MAX_CONSECUTIVE_FAILURES - 1
    push.deliver(notification)
    assert PushSubscription.objects.count() == 0


def test_deliver_is_a_noop_without_keys(monkeypatch):
    fam = make_family()
    monkeypatch.setattr(push, "webpush", lambda *a, **kw: pytest.fail("must not send without keys"))
    notification = ParentNotification.objects.create(
        parent=_parent(), kind=ParentNotification.Kind.SYSTEM, title="Тест", body=""
    )
    assert push.deliver(notification) == {"sent": 0, "gone": 0, "failed": 0}
    assert fam["parent"].get(CONFIG_URL).json()["enabled"] is False


def test_real_encryption_pipeline_with_generated_keys(vapid, monkeypatch, tmp_path):
    """The key formats we store work end to end in pywebpush (``curl=True`` builds the request without sending)."""
    monkeypatch.chdir(tmp_path)  # pywebpush writes encrypted.data into the CWD when curl=True
    command = webpush(
        {"endpoint": ENDPOINT, "keys": _client_keys()},
        data=json.dumps({"title": "Проверка"}, ensure_ascii=False),
        vapid_private_key=PRIVATE,
        vapid_claims={"sub": SUBJECT},
        ttl=60,
        curl=True,
    )
    assert ENDPOINT in command
    assert "vapid" in command.lower()
    assert "aes128gcm" in command


# ---------------------------------------------------------------------------
# Scheduling from notification creation
# ---------------------------------------------------------------------------
def test_notifications_push_after_commit(vapid, monkeypatch):
    fam = make_family()
    assert _subscribe(fam["parent"]).status_code == 201
    sent: list[dict] = []
    monkeypatch.setattr(push, "webpush", lambda subscription_info, data, **kw: sent.append(json.loads(data)))
    student = StudentProfile.objects.get(pk=fam["child"]["id"])

    with TestCase.captureOnCommitCallbacks(execute=True) as callbacks:
        created = services.notify_parents(
            student, kind=ParentNotification.Kind.SYSTEM, title="Привет", body="Текст"
        )
    assert len(created) == 1 and len(callbacks) == 1
    assert [p["notification_id"] for p in sent] == [str(created[0].id)]

    with TestCase.captureOnCommitCallbacks(execute=True):
        _notify_parents_about_lockout(student, permanent=False)
    assert len(sent) == 2
    assert sent[1]["title"] == "Несколько неверных PIN подряд"
    assert ParentNotification.objects.filter(kind=ParentNotification.Kind.SYSTEM).count() == 2


def test_nothing_is_scheduled_without_keys():
    fam = make_family()
    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    with TestCase.captureOnCommitCallbacks() as callbacks:
        services.notify_parents(student, kind=ParentNotification.Kind.SYSTEM, title="t", body="b")
    assert callbacks == []
    assert ParentNotification.objects.count() == 1


# ---------------------------------------------------------------------------
# VAPID tooling
# ---------------------------------------------------------------------------
def test_vapid_keys_command_prints_a_matching_pair():
    out = StringIO()
    call_command("vapid_keys", "--subject", "mailto:team@example.kg", stdout=out)
    lines = dict(
        line.split("=", 1) for line in out.getvalue().splitlines() if "=" in line and not line.startswith("#")
    )
    assert set(lines) == {"VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_SUBJECT"}
    assert push.derive_public_key(lines["VAPID_PRIVATE_KEY"]) == lines["VAPID_PUBLIC_KEY"]
    assert lines["VAPID_SUBJECT"] == "mailto:team@example.kg"


def test_system_check_catches_misconfiguration(settings):
    def ids():
        return sorted(error.id for error in checks.check_webpush_configuration(None))

    assert ids() == []  # unset → push off, nothing to complain about

    settings.WEBPUSH_VAPID_PRIVATE_KEY = PRIVATE
    settings.WEBPUSH_VAPID_PUBLIC_KEY = ""
    assert ids() == ["parents.E001"]

    settings.WEBPUSH_VAPID_PUBLIC_KEY = push.generate_keypair()[1]
    settings.WEBPUSH_VAPID_SUBJECT = ""
    assert ids() == ["parents.E003", "parents.E004"]

    settings.WEBPUSH_VAPID_PRIVATE_KEY = "not-a-key"
    assert ids() == ["parents.E002"]

    settings.WEBPUSH_VAPID_PRIVATE_KEY = PRIVATE
    settings.WEBPUSH_VAPID_PUBLIC_KEY = PUBLIC
    settings.WEBPUSH_VAPID_SUBJECT = SUBJECT
    assert ids() == []


# ---------------------------------------------------------------------------
# Review follow-ups: device limit, robustness, revocation
# ---------------------------------------------------------------------------
def test_a_parent_keeps_only_the_newest_devices(vapid):
    fam = make_family()
    for index in range(push.MAX_DEVICES_PER_PARENT + 2):
        assert _subscribe(fam["parent"], f"{ENDPOINT}-{index}").status_code == 201
    endpoints = set(PushSubscription.objects.values_list("endpoint", flat=True))
    assert len(endpoints) == push.MAX_DEVICES_PER_PARENT
    assert f"{ENDPOINT}-0" not in endpoints and f"{ENDPOINT}-1" not in endpoints
    assert f"{ENDPOINT}-{push.MAX_DEVICES_PER_PARENT + 1}" in endpoints


def test_broken_keys_do_not_stop_the_other_devices(vapid, monkeypatch):
    fam = make_family()
    assert _subscribe(fam["parent"]).status_code == 201
    assert _subscribe(fam["parent"], ENDPOINT + "-broken").status_code == 201

    def exploding_webpush(subscription_info, data, **kwargs):
        if subscription_info["endpoint"].endswith("-broken"):
            raise ValueError("Invalid EC key")
        return FakeResponse(201)

    monkeypatch.setattr(push, "webpush", exploding_webpush)
    notification = ParentNotification.objects.create(
        parent=_parent(), kind=ParentNotification.Kind.SYSTEM, title="Тест", body=""
    )
    assert push.deliver(notification) == {"sent": 1, "gone": 0, "failed": 1}
    assert PushSubscription.objects.get(endpoint=ENDPOINT + "-broken").failures == 1


def test_inactive_parent_gets_nothing(vapid, monkeypatch):
    fam = make_family()
    assert _subscribe(fam["parent"]).status_code == 201
    monkeypatch.setattr(push, "webpush", lambda *a, **kw: pytest.fail("must not push to a closed account"))
    parent = _parent()
    parent.user.is_active = False
    parent.user.save(update_fields=["is_active"])
    notification = ParentNotification.objects.create(
        parent=parent, kind=ParentNotification.Kind.SYSTEM, title="Тест"
    )
    assert push.deliver(notification) == {"sent": 0, "gone": 0, "failed": 0}


def test_revoked_sessions_and_family_deletion_drop_devices(vapid):
    fam = make_family()
    assert _subscribe(fam["parent"]).status_code == 201
    assert revoke_user_sessions(_parent().user) >= 1
    assert PushSubscription.objects.count() == 0

    assert _subscribe(fam["parent"]).status_code == 201
    deleted = fam["parent"].post(
        "/api/v1/parents/family/delete/", {"password": "Strong-pass-123", "confirm": True}, format="json"
    )
    assert deleted.status_code == 200, deleted.content
    assert PushSubscription.objects.count() == 0
