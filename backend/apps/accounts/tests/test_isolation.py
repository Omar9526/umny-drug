"""Family isolation: no user may read or change another family's data, whatever id they guess."""

import pytest

from apps.tutor.models import LearningSession

from .helpers import make_family

pytestmark = pytest.mark.django_db


def test_parent_cannot_access_child_of_another_family():
    a = make_family(email="a@example.com", nickname="Алина")
    b = make_family(email="b@example.com", nickname="Бекзат")

    foreign_child_id = b["child"]["id"]
    assert a["parent"].get(f"/api/v1/parents/children/{foreign_child_id}/").status_code == 404
    assert (
        a["parent"].patch(f"/api/v1/parents/children/{foreign_child_id}/", {"nickname": "X"}).status_code
        == 404
    )
    assert (
        a["parent"].post(f"/api/v1/parents/children/{foreign_child_id}/pin/", {"pin": "1357"}).status_code
        == 404
    )
    assert a["parent"].delete(f"/api/v1/parents/children/{foreign_child_id}/").status_code == 404

    own = a["parent"].get("/api/v1/parents/children/").json()
    assert [c["nickname"] for c in own] == ["Алина"]


def test_history_is_scoped_to_family_and_student():
    a = make_family(email="a@example.com")
    b = make_family(email="b@example.com", nickname="Бекзат")

    from apps.accounts.models import StudentProfile

    student_a = StudentProfile.objects.get(id=a["child"]["id"])
    student_b = StudentProfile.objects.get(id=b["child"]["id"])
    LearningSession.objects.create(
        student=student_a, family=student_a.family, grade=student_a.grade, title="A"
    )
    LearningSession.objects.create(
        student=student_b, family=student_b.family, grade=student_b.grade, title="B"
    )

    titles_a = [s["title"] for s in a["student"].get("/api/v1/learning/history/").json()["results"]]
    assert titles_a == ["A"]

    # Parent B asking for child A's history by id gets nothing, not an error leaking existence.
    leak = b["parent"].get(f"/api/v1/learning/history/?student={student_a.id}").json()["results"]
    assert leak == []
    titles_parent_b = [s["title"] for s in b["parent"].get("/api/v1/learning/history/").json()["results"]]
    assert titles_parent_b == ["B"]


def test_role_gates():
    fam = make_family(email="a@example.com")
    assert fam["student"].get("/api/v1/parents/children/").status_code == 403
    assert fam["student"].get("/api/v1/parents/family/").status_code == 403
    assert fam["parent"].get("/api/v1/students/me/").status_code == 403
    assert fam["parent"].get("/api/v1/students/me/dashboard/").status_code == 403


def test_anonymous_is_rejected():
    from rest_framework.test import APIClient

    anon = APIClient()
    assert anon.get("/api/v1/students/me/").status_code == 401
    assert anon.get("/api/v1/parents/children/").status_code == 401
    assert anon.get("/api/v1/learning/history/").status_code == 401
    assert anon.get("/api/v1/subjects/").status_code == 401


def test_deactivated_child_cannot_log_in_and_disappears_from_lookup():
    fam = make_family(email="a@example.com")
    child_id = fam["child"]["id"]
    assert fam["parent"].delete(f"/api/v1/parents/children/{child_id}/").status_code == 204

    from rest_framework.test import APIClient

    lookup = APIClient().post(
        "/api/v1/auth/child/lookup/", {"family_code": fam["family_code"]}, format="json"
    )
    assert lookup.json()["children"] == []
    login = APIClient().post(
        "/api/v1/auth/child/login/",
        {"family_code": fam["family_code"], "student_id": child_id, "pin": "2468"},
        format="json",
    )
    assert login.status_code == 401
    # Existing access token of the deactivated child is no longer accepted.
    assert fam["student"].get("/api/v1/students/me/").status_code == 401
