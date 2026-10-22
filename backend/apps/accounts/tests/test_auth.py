import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import ConsentRecord, StudentProfile, User

from .helpers import (
    CHILD_LOGIN_URL,
    CHILD_LOOKUP_URL,
    LOGIN_URL,
    REGISTER_URL,
    auth_client,
    child_login,
    create_child,
    register_parent,
)

pytestmark = pytest.mark.django_db


def test_parent_registration_creates_family_and_consents():
    client = APIClient()
    response = register_parent(client)
    body = response.json()

    assert body["access"]
    assert settings.AUTH_COOKIE_NAME in response.cookies
    assert response.cookies[settings.AUTH_COOKIE_NAME]["httponly"]
    assert body["user"]["role"] == "parent"
    assert len(body["user"]["parent"]["family"]["code"]) == 6

    user = User.objects.get(email="parent@example.com")
    assert user.family is not None
    assert set(user.consents.values_list("consent_type", flat=True)) == {"terms", "privacy"}


def test_registration_requires_consents():
    response = APIClient().post(
        REGISTER_URL,
        {
            "display_name": "Бакыт",
            "email": "x@example.com",
            "password": "Strong-pass-123",
            "consents": {"terms": True, "privacy": False},
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "consents" in response.json()["error"]["details"]


def test_duplicate_email_is_rejected_with_field_error():
    register_parent(APIClient())
    response = APIClient().post(
        REGISTER_URL,
        {
            "display_name": "Другой",
            "email": "parent@example.com",
            "password": "Strong-pass-123",
            "consents": {"terms": True, "privacy": True},
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "email" in response.json()["error"]["details"]


def test_login_error_does_not_reveal_whether_user_exists():
    register_parent(APIClient())
    wrong_pw = APIClient().post(LOGIN_URL, {"email": "parent@example.com", "password": "nope"}, format="json")
    unknown = APIClient().post(LOGIN_URL, {"email": "ghost@example.com", "password": "nope"}, format="json")
    assert wrong_pw.status_code == unknown.status_code == 400
    assert wrong_pw.json()["error"]["details"] == unknown.json()["error"]["details"]


def test_refresh_rotates_cookie_and_logout_clears_it():
    client = APIClient()
    register_parent(client)
    first_cookie = client.cookies[settings.AUTH_COOKIE_NAME].value

    refreshed = client.post("/api/v1/auth/token/refresh/")
    assert refreshed.status_code == 200
    assert refreshed.json()["access"]
    assert refreshed.json()["user"]["role"] == "parent"
    second_cookie = client.cookies[settings.AUTH_COOKIE_NAME].value
    assert second_cookie != first_cookie

    # The old refresh token is blacklisted after rotation.
    stale = APIClient()
    stale.cookies[settings.AUTH_COOKIE_NAME] = first_cookie
    assert stale.post("/api/v1/auth/token/refresh/").status_code == 401

    logout = client.post("/api/v1/auth/logout/")
    assert logout.status_code == 204
    assert client.cookies[settings.AUTH_COOKIE_NAME].value == ""


def test_child_login_flow():
    reg = register_parent(APIClient()).json()
    parent = auth_client(reg["access"])
    family_code = reg["user"]["parent"]["family"]["code"]
    child = create_child(parent, pin="2468")

    student = StudentProfile.objects.get(id=child["id"])
    assert student.consents.filter(granted=True).count() == 2
    assert ConsentRecord.Type.CHILD_DATA in student.consents.values_list("consent_type", flat=True)

    lookup = APIClient().post(CHILD_LOOKUP_URL, {"family_code": family_code.lower()}, format="json")
    assert lookup.status_code == 200
    assert lookup.json()["children"][0]["nickname"] == "Алина"
    assert set(lookup.json()["children"][0]) == {"id", "nickname", "avatar", "grade_number"}

    login = child_login(family_code, child["id"], "2468")
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["role"] == "student"
    assert "email" not in body["user"]
    assert body["user"]["student"]["grade"]["number"] == 5


def test_child_pin_lockout_after_failed_attempts():
    reg = register_parent(APIClient()).json()
    parent = auth_client(reg["access"])
    family_code = reg["user"]["parent"]["family"]["code"]
    child = create_child(parent, pin="2468")

    for _ in range(settings.CHILD_PIN_MAX_ATTEMPTS - 1):
        assert child_login(family_code, child["id"], "0000").status_code == 401
    locked = child_login(family_code, child["id"], "0000")
    assert locked.status_code == 423
    # Even the correct PIN is refused while locked.
    assert child_login(family_code, child["id"], "2468").status_code == 423


def test_unknown_family_code_is_rejected():
    response = APIClient().post(CHILD_LOOKUP_URL, {"family_code": "ZZZZZZ"}, format="json")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_child_login_is_throttled_per_code():
    reg = register_parent(APIClient()).json()
    parent = auth_client(reg["access"])
    family_code = reg["user"]["parent"]["family"]["code"]
    child = create_child(parent, pin="2468")

    statuses = []
    client = APIClient()
    for _ in range(12):
        statuses.append(
            client.post(
                CHILD_LOGIN_URL,
                {"family_code": family_code, "student_id": child["id"], "pin": "1111"},
                format="json",
            ).status_code
        )
    assert 429 in statuses


def test_weak_pin_is_rejected():
    reg = register_parent(APIClient()).json()
    parent = auth_client(reg["access"])
    response = parent.post(
        "/api/v1/parents/children/",
        {"nickname": "Б", "grade_id": 1, "pin": "1111", "consent_confirmed": True},
        format="json",
    )
    assert response.status_code == 400
    assert "pin" in response.json()["error"]["details"]
