import pytest

from .helpers import make_family

pytestmark = pytest.mark.django_db


def test_dashboard_returns_real_zero_stats_and_grade_subjects():
    fam = make_family(email="a@example.com", grade=5)
    response = fam["student"].get("/api/v1/students/me/dashboard/")
    assert response.status_code == 200
    body = response.json()

    assert body["student"]["nickname"] == "Алина"
    assert body["demo_mode"] is True
    assert body["continue_session"] is None
    assert body["recent_sessions"] == []
    assert body["stats"] == {
        "sessions_total": 0,
        "completed_total": 0,
        "week_sessions": 0,
        "week_independent": 0,
    }

    slugs = {s["slug"] for s in body["subjects"]}
    assert "math" in slugs and "russian" in slugs and "history" in slugs
    assert "algebra" not in slugs  # grade 7+
    math = next(s for s in body["subjects"] if s["slug"] == "math")
    assert math["topics_count"] > 10


def test_student_can_update_profile_and_finish_onboarding():
    fam = make_family(email="a@example.com", grade=5)
    response = fam["student"].patch(
        "/api/v1/students/me/",
        {"avatar": "robot", "explanation_language": "ky", "onboarding_completed": True},
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["avatar"] == "robot"
    assert body["explanation_language"] == "ky"
    assert body["onboarding_completed"] is True

    bad = fam["student"].patch("/api/v1/students/me/", {"avatar": "dragon"}, format="json")
    assert bad.status_code == 400


def test_subject_detail_lists_sections_with_progress_status():
    fam = make_family(email="a@example.com", grade=5)
    response = fam["student"].get("/api/v1/subjects/math/")
    assert response.status_code == 200
    body = response.json()
    assert body["grade"]["number"] == 5
    assert body["sections"]
    topic = body["sections"][0]["topics"][0]
    assert topic["progress_status"] == "not_started"

    other_grade = fam["student"].get("/api/v1/subjects/algebra/")
    assert other_grade.status_code == 404


def test_curricula_are_public():
    from rest_framework.test import APIClient

    response = APIClient().get("/api/v1/curricula/")
    assert response.status_code == 200
    kg = response.json()[0]
    assert kg["code"] == "kg"
    assert [g["number"] for g in kg["grades"]] == list(range(1, 12))
