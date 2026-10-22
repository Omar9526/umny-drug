"""Abuse-resistance: spoofed proxy headers, PIN lockout escalation, session revocation, CSRF origin."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ConsentRecord, StudentProfile
from apps.core.network import client_ip
from apps.parents.models import ParentNotification

from .helpers import (
    CHILD_LOGIN_URL,
    CHILD_LOOKUP_URL,
    REGISTER_URL,
    child_login,
    make_family,
    register_parent,
)

pytestmark = pytest.mark.django_db


def test_spoofed_x_forwarded_for_does_not_bypass_throttle():
    client = APIClient()
    statuses = []
    for i in range(25):
        statuses.append(
            client.post(
                CHILD_LOOKUP_URL,
                {"family_code": "ZZZZZZ"},
                format="json",
                HTTP_X_FORWARDED_FOR=f"10.0.{i // 250}.{i % 250}",
            ).status_code
        )
    assert 429 in statuses


def test_garbage_forwarded_header_never_reaches_ip_columns():
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        {
            "display_name": "Нурлан",
            "email": "xff@example.com",
            "password": "Strong-pass-123",
            "consents": {"terms": True, "privacy": True},
        },
        format="json",
        HTTP_X_FORWARDED_FOR="not-an-ip, 1.2.3.4:5678",
    )
    assert response.status_code == 201
    consent = ConsentRecord.objects.get(granted_by__email="xff@example.com", consent_type="terms")
    assert consent.ip_address == "127.0.0.1"  # REMOTE_ADDR of the test client; header ignored


def test_client_ip_honours_num_proxies(rf):
    request = rf.get("/", HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.2", REMOTE_ADDR="10.0.0.1")
    assert client_ip(request) == "10.0.0.1"
    with override_settings(NUM_PROXIES=1):
        assert client_ip(request) == "10.0.0.2"
    with override_settings(NUM_PROXIES=2):
        assert client_ip(request) == "203.0.113.9"
    bad = rf.get("/", HTTP_X_FORWARDED_FOR="evil", REMOTE_ADDR="10.0.0.1")
    with override_settings(NUM_PROXIES=1):
        assert client_ip(bad) == "10.0.0.1"


def test_pin_lockout_escalates_and_finally_requires_parent_reset():
    fam = make_family(email="a@example.com", pin="2468")
    student = StudentProfile.objects.get(id=fam["child"]["id"])
    code = fam["family_code"]

    for cycle in range(1, settings.CHILD_PIN_MAX_LOCKOUTS + 1):
        cache.clear()  # throttling is covered by its own test; here we exercise the lockout state machine
        for _ in range(settings.CHILD_PIN_MAX_ATTEMPTS - 1):
            assert child_login(code, student.id, "0000").status_code == 401
        locked = child_login(code, student.id, "0000")
        assert locked.status_code == 423
        student.refresh_from_db()
        assert student.pin_lockouts == cycle
        if cycle < settings.CHILD_PIN_MAX_LOCKOUTS:
            assert locked.json()["error"]["code"] == "account_locked"
            # Each lockout lasts longer than the previous one.
            expected = settings.CHILD_PIN_LOCK_MINUTES * (2 ** (cycle - 1))
            remaining = student.pin_locked_until - timezone.now()
            assert timedelta(minutes=expected - 1) < remaining <= timedelta(minutes=expected)
            # Simulate the lock expiring.
            StudentProfile.objects.filter(id=student.id).update(
                pin_locked_until=timezone.now() - timedelta(seconds=1)
            )
        else:
            assert locked.json()["error"]["code"] == "pin_reset_required"
            assert student.pin_requires_parent_reset is True

    cache.clear()
    # Correct PIN is refused until a parent resets it; parents were notified.
    assert child_login(code, student.id, "2468").status_code == 423
    assert ParentNotification.objects.filter(student=student).count() == settings.CHILD_PIN_MAX_LOCKOUTS

    assert (
        fam["parent"].post(f"/api/v1/parents/children/{student.id}/pin/", {"pin": "1357"}).status_code == 204
    )
    assert child_login(code, student.id, "1357").status_code == 200


def test_pin_reset_revokes_existing_child_sessions():
    fam = make_family(email="a@example.com", pin="2468")
    child_id = fam["child"]["id"]
    browser = APIClient()
    login = browser.post(
        CHILD_LOGIN_URL,
        {"family_code": fam["family_code"], "student_id": child_id, "pin": "2468"},
        format="json",
    )
    assert login.status_code == 200
    assert browser.post("/api/v1/auth/token/refresh/").status_code == 200

    assert fam["parent"].post(f"/api/v1/parents/children/{child_id}/pin/", {"pin": "1357"}).status_code == 204
    assert browser.post("/api/v1/auth/token/refresh/").status_code == 401


def test_family_code_rotation_revokes_child_sessions():
    fam = make_family(email="a@example.com", pin="2468")
    browser = APIClient()
    browser.post(
        CHILD_LOGIN_URL,
        {"family_code": fam["family_code"], "student_id": fam["child"]["id"], "pin": "2468"},
        format="json",
    )
    assert fam["parent"].post("/api/v1/parents/family/rotate-code/").status_code == 200
    assert browser.post("/api/v1/auth/token/refresh/").status_code == 401


def test_invalid_refresh_does_not_delete_cookie_of_winning_tab():
    client = APIClient()
    register_parent(client)
    first = client.cookies[settings.AUTH_COOKIE_NAME].value
    assert client.post("/api/v1/auth/token/refresh/").status_code == 200
    rotated = client.cookies[settings.AUTH_COOKIE_NAME].value

    loser = APIClient()
    loser.cookies[settings.AUTH_COOKIE_NAME] = first
    response = loser.post("/api/v1/auth/token/refresh/")
    assert response.status_code == 401
    assert settings.AUTH_COOKIE_NAME not in response.cookies  # no Set-Cookie deletion
    assert rotated != first


def test_refresh_and_logout_reject_foreign_origin():
    client = APIClient()
    register_parent(client)
    assert client.post("/api/v1/auth/token/refresh/", HTTP_ORIGIN="https://evil.example").status_code == 403
    assert client.post("/api/v1/auth/logout/", HTTP_ORIGIN="https://evil.example").status_code == 403
    assert client.post("/api/v1/auth/token/refresh/", HTTP_ORIGIN="http://localhost:3000").status_code == 200


def test_password_errors_are_reported_on_the_field():
    response = APIClient().post(
        REGISTER_URL,
        {
            "display_name": "Айгуль",
            "email": "aigul@example.com",
            "password": "aigul@example.com",
            "consents": {"terms": True, "privacy": True},
        },
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]
