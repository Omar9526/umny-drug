"""Knowledge map: honest statuses per topic, the next step, parent scoping."""

from __future__ import annotations

import pytest

from apps.accounts.models import StudentProfile
from apps.accounts.tests.helpers import make_family
from apps.learning.models import KnowledgeMapNode, LearningProgress

pytestmark = pytest.mark.django_db

MAP = "/api/v1/learning/map/"


def test_map_lists_the_route_with_statuses_and_next_step():
    fam = make_family()
    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    response = fam["student"].get(MAP + "?subject=math")
    assert response.status_code == 200, response.content
    body = response.json()
    expected = KnowledgeMapNode.objects.filter(route_key="math-5").count()
    assert body["subject"]["slug"] == "math" and body["grade"]["number"] == 5
    assert body["summary"]["total"] == len(body["nodes"]) == expected > 0
    assert {n["status"] for n in body["nodes"]} == {"not_started"}
    assert body["next_topic_id"] == body["nodes"][0]["topic_id"]
    assert [n["order"] for n in body["nodes"]] == list(range(expected))
    assert all(0 <= n["x"] <= 100 for n in body["nodes"])

    first, second, third = body["nodes"][:3]
    LearningProgress.objects.create(
        student=student, family=student.family, topic_id=second["topic_id"], status="learning"
    )
    LearningProgress.objects.create(
        student=student, family=student.family, topic_id=third["topic_id"], status="needs_review"
    )
    LearningProgress.objects.create(
        student=student, family=student.family, topic_id=first["topic_id"], status="mastered"
    )
    body = fam["student"].get(MAP + "?subject=math").json()
    assert body["next_topic_id"] == third["topic_id"], "needs_review comes before learning"
    assert body["summary"] == {
        "total": expected,
        "not_started": expected - 3,
        "learning": 1,
        "completed": 0,
        "needs_review": 1,
        "mastered": 1,
    }
    assert body["nodes"][0]["status"] == "mastered"


def test_map_validation_and_parent_scope():
    a = make_family(email="a@example.com")
    b = make_family(email="b@example.com")
    child_a = a["child"]["id"]
    assert a["student"].get(MAP).status_code == 400
    assert a["student"].get(MAP + "?subject=nope").status_code == 404
    assert a["parent"].get(MAP + "?subject=math").status_code == 404, "parent must name a child"
    assert a["parent"].get(f"{MAP}?subject=math&student={child_a}").status_code == 200
    assert b["parent"].get(f"{MAP}?subject=math&student={child_a}").status_code == 404


def test_topic_detail_carries_an_honest_progress_block():
    fam = make_family()
    body = fam["student"].get(MAP + "?subject=math").json()
    topic_id = body["nodes"][0]["topic_id"]
    detail = fam["student"].get(f"/api/v1/topics/{topic_id}/")
    assert detail.status_code == 200, detail.content
    data = detail.json()
    assert data["progress_status"] == "not_started"
    assert data["progress"] is None and data["last_quiz"] is None and data["recent_sessions"] == []
    assert data["subject"]["slug"] == "math"
