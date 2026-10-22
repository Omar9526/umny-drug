"""Shared helpers for API tests: register parents, create children, log children in."""

from __future__ import annotations

from rest_framework.test import APIClient

from apps.curriculum.models import Grade

REGISTER_URL = "/api/v1/auth/parent/register/"
LOGIN_URL = "/api/v1/auth/login/"
CHILDREN_URL = "/api/v1/parents/children/"
CHILD_LOOKUP_URL = "/api/v1/auth/child/lookup/"
CHILD_LOGIN_URL = "/api/v1/auth/child/login/"


def register_parent(client: APIClient, email: str = "parent@example.com", password: str = "Strong-pass-123"):
    response = client.post(
        REGISTER_URL,
        {
            "display_name": "Айгуль",
            "email": email,
            "password": password,
            "preferred_language": "ru",
            "consents": {"terms": True, "privacy": True, "marketing": False},
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response


def auth_client(access: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def grade_id(number: int = 5) -> int:
    return Grade.objects.get(curriculum__code="kg", number=number).id


def create_child(parent_client: APIClient, nickname: str = "Алина", grade: int = 5, pin: str = "2468"):
    response = parent_client.post(
        CHILDREN_URL,
        {
            "nickname": nickname,
            "grade_id": grade_id(grade),
            "instruction_language": "ru",
            "explanation_language": "ru",
            "avatar": "owl",
            "pin": pin,
            "consent_confirmed": True,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def child_login(family_code: str, student_id: str, pin: str = "2468"):
    client = APIClient()
    return client.post(
        CHILD_LOGIN_URL, {"family_code": family_code, "student_id": student_id, "pin": pin}, format="json"
    )


def make_family(
    email: str = "parent@example.com", nickname: str = "Алина", grade: int = 5, pin: str = "2468"
):
    """Parent + one child, both authenticated. Returns dict with clients and ids."""
    anon = APIClient()
    reg = register_parent(anon, email=email).json()
    parent = auth_client(reg["access"])
    family_code = reg["user"]["parent"]["family"]["code"]
    child = create_child(parent, nickname=nickname, grade=grade, pin=pin)
    login = child_login(family_code, child["id"], pin)
    assert login.status_code == 200, login.content
    student = auth_client(login.json()["access"])
    return {
        "parent": parent,
        "student": student,
        "family_code": family_code,
        "child": child,
        "parent_user": reg["user"],
    }
