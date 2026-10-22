"""Parent cabinet: real aggregates, transparency rules, parental controls, consents and erasure."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ConsentRecord, StudentProfile, User
from apps.accounts.tests.helpers import make_family
from apps.curriculum.models import Topic
from apps.learning.models import LearningProgress
from apps.parents import services
from apps.tutor.models import LearningSession
from apps.tutor.services import complete_session
from apps.tutor.tests.fakes import fake_provider  # noqa: F401 - fixture
from apps.tutor.tests.helpers import parse_sse

pytestmark = pytest.mark.django_db

Outcome = LearningSession.Outcome
Status = LearningSession.Status
FINISHED = (Outcome.UNDERSTOOD_INDEPENDENTLY, Outcome.COMPLETED_WITH_HELP, Outcome.NEEDS_REVIEW)


def _topics(n: int = 2) -> list[Topic]:
    qs = Topic.objects.filter(section__subject__slug="math", section__grade__number=5).order_by("id")
    topics = list(qs[:n])
    assert len(topics) == n, "seeded curriculum expected"
    return topics


def _session(student: StudentProfile, topic: Topic, *, outcome: str, days_ago: int = 1, **extra):
    when = timezone.now() - timedelta(days=days_ago)
    session = LearningSession.objects.create(
        student=student,
        family=student.family,
        grade=student.grade,
        subject=topic.section.subject,
        topic=topic,
        mode=LearningSession.Mode.HOMEWORK,
        status=Status.COMPLETED if outcome in FINISHED else Status.ABANDONED,
        outcome=outcome,
        title=topic.name_ru,
        last_activity_at=when,
        ended_at=when,
        **extra,
    )
    LearningSession.objects.filter(pk=session.pk).update(created_at=when)
    return session


def _start_question_session(student_client, question="12 * 4 = ?") -> str:
    created = student_client.post(
        "/api/v1/tutor/sessions/", {"mode": "question", "question": question}, format="json"
    )
    assert created.status_code == 201, created.content
    session_id = created.json()["id"]
    parse_sse(
        student_client.post(
            f"/api/v1/tutor/sessions/{session_id}/messages/",
            {"command": "start", "content": question},
            format="json",
        )
    )
    return session_id


def test_overview_is_honest_without_data():
    fam = make_family()
    response = fam["parent"].get("/api/v1/parents/overview/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["family_code"].replace("-", "") == fam["family_code"]
    assert body["unread_notifications"] == 0
    child = body["children"][0]
    assert child["child"]["id"] == fam["child"]["id"]
    assert child["summary"]["sessions_total"] == 0
    assert child["summary"]["last_activity_at"] is None
    assert child["summary"]["difficult_topics"] == []


def test_progress_report_and_recommendations_come_from_real_sessions():
    fam = make_family()
    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    easy, hard = _topics(2)
    _session(student, easy, outcome=Outcome.UNDERSTOOD_INDEPENDENTLY, days_ago=1, correct_attempts=1)
    _session(student, easy, outcome=Outcome.UNDERSTOOD_INDEPENDENTLY, days_ago=2, correct_attempts=1)
    _session(student, hard, outcome=Outcome.NEEDS_REVIEW, days_ago=3, hints_used=3, attempts_count=2)
    _session(
        student, hard, outcome=Outcome.COMPLETED_WITH_HELP, days_ago=20, hints_used=2, correct_attempts=1
    )
    LearningProgress.objects.create(
        student=student,
        family=student.family,
        topic=hard,
        status=LearningProgress.Status.NEEDS_REVIEW,
        sessions_count=2,
        attempts_count=5,
        correct_count=1,
        hints_count=5,
        last_activity_at=timezone.now(),
    )

    response = fam["parent"].get(f"/api/v1/parents/children/{student.id}/progress/")
    assert response.status_code == 200, response.content
    body = response.json()

    summary = body["summary"]
    assert summary["sessions_total"] == 4
    assert summary["sessions_week"] == 3
    assert summary["independent_week"] == 2
    assert summary["needs_review_week"] == 1

    report = body["weekly_report"]
    assert report["has_data"] is True
    assert (report["sessions"], report["independent"], report["needs_review"]) == (3, 2, 1)
    assert report["text"].startswith("Алина на этой неделе: 3 задания.")
    assert "2 решены самостоятельно" in report["text"]
    assert "1 требует повторения" in report["text"]
    assert any(hard.name_ru in h for h in report["highlights"])

    assert [t["topic_id"] for t in body["difficult_topics"]] == [hard.id]
    review = next(r for r in body["recommendations"] if r["kind"] == "review_topic")
    assert review["action"] == {"type": "explain_topic", "topic_id": hard.id, "subject_slug": "math"}

    math = next(s for s in body["subjects"] if s["subject"]["slug"] == "math")
    assert (math["sessions"], math["independent"], math["needs_review"]) == (4, 2, 1)
    assert math["topics"] == {"needs_review": 1}
    assert len(body["recent_sessions"]) == 4


def test_needs_review_session_without_topic_is_recommended_for_review():
    fam = make_family()
    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    (topic,) = _topics(1)
    session = _session(student, topic, outcome=Outcome.NEEDS_REVIEW, days_ago=1, attempts_count=1)
    session.topic = None
    session.title = "7 * 8 = ?"
    session.save(update_fields=["topic", "title"])

    body = fam["parent"].get(f"/api/v1/parents/children/{student.id}/progress/").json()
    item = next(r for r in body["recommendations"] if r["kind"] == "review_session")
    assert "7 * 8 = ?" in item["title"]
    assert item["action"] == {"type": "session", "session_id": str(session.id)}


def test_inactive_child_gets_a_gentle_nudge():
    fam = make_family()
    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    (topic,) = _topics(1)
    _session(student, topic, outcome=Outcome.UNDERSTOOD_INDEPENDENTLY, days_ago=12, correct_attempts=1)
    body = fam["parent"].get(f"/api/v1/parents/children/{student.id}/progress/").json()
    assert body["weekly_report"]["has_data"] is False
    nudge = next(r for r in body["recommendations"] if r["kind"] == "inactive")
    assert "12 дней" in nudge["text"]
    assert nudge["action"] == {"type": "photo"}


def test_parent_sees_dialogue_only_when_child_profile_allows(fake_provider):  # noqa: F811
    fam = make_family()
    child_id = fam["child"]["id"]
    session_id = _start_question_session(fam["student"])

    visible = fam["parent"].get(f"/api/v1/parents/children/{child_id}/sessions/{session_id}/")
    assert visible.status_code == 200, visible.content
    assert visible.json()["conversation_visible"] is True
    assert len(visible.json()["messages"]) >= 2

    patched = fam["parent"].patch(
        f"/api/v1/parents/children/{child_id}/", {"share_conversations_with_parent": False}, format="json"
    )
    assert patched.status_code == 200, patched.content
    assert patched.json()["share_conversations_with_parent"] is False

    hidden = fam["parent"].get(f"/api/v1/parents/children/{child_id}/sessions/{session_id}/").json()
    assert hidden["conversation_visible"] is False
    assert hidden["messages"] == []
    assert hidden["status"] == "active"  # outcome data stays visible

    listed = fam["parent"].get(f"/api/v1/parents/children/{child_id}/sessions/")
    assert listed.status_code == 200
    assert [s["id"] for s in listed.json()["results"]] == [session_id]
    filtered = fam["parent"].get(f"/api/v1/parents/children/{child_id}/sessions/?outcome=needs_review")
    assert filtered.json()["count"] == 0


def test_other_family_cannot_read_child_or_sessions(fake_provider):  # noqa: F811
    a = make_family(email="a@example.com")
    b = make_family(email="b@example.com")
    session_id = _start_question_session(a["student"])
    child_id = a["child"]["id"]
    assert b["parent"].get(f"/api/v1/parents/children/{child_id}/").status_code == 404
    assert b["parent"].get(f"/api/v1/parents/children/{child_id}/progress/").status_code == 404
    assert b["parent"].get(f"/api/v1/parents/children/{child_id}/sessions/{session_id}/").status_code == 404
    assert b["parent"].post(f"/api/v1/parents/children/{child_id}/erase/").status_code == 404
    assert a["student"].get("/api/v1/parents/overview/").status_code == 403


def test_parental_controls_are_enforced_server_side(fake_provider):  # noqa: F811
    fam = make_family()
    child_id = fam["child"]["id"]
    fam["parent"].patch(
        f"/api/v1/parents/children/{child_id}/",
        {"allow_photo_upload": False, "allow_free_questions": False},
        format="json",
    )
    photo = fam["student"].post("/api/v1/assignments/upload/", {"source": "camera"}, format="multipart")
    assert photo.status_code == 403
    assert photo.json()["error"]["code"] == "feature_disabled"

    typed = fam["student"].post(
        "/api/v1/assignments/upload/", {"source": "text", "typed_text": "2 + 2 = ?"}, format="multipart"
    )
    assert typed.status_code == 201, typed.content

    question = fam["student"].post(
        "/api/v1/tutor/sessions/", {"mode": "question", "question": "Что такое дробь?"}, format="json"
    )
    assert question.status_code == 403
    assert question.json()["error"]["code"] == "feature_disabled"

    me = fam["student"].get("/api/v1/auth/me/").json()
    assert me["student"]["allow_photo_upload"] is False
    assert me["student"]["allow_free_questions"] is False


def test_needs_review_outcome_notifies_parent_once_per_day():
    fam = make_family()
    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    (topic,) = _topics(1)
    for _ in range(2):
        session = LearningSession.objects.create(
            student=student,
            family=student.family,
            grade=student.grade,
            subject=topic.section.subject,
            topic=topic,
            mode=LearningSession.Mode.HOMEWORK,
            title=topic.name_ru,
            attempts_count=2,
            solution_revealed=True,
        )
        with transaction.atomic():
            session = complete_session(session=session, reason="manual")
        assert session.outcome == Outcome.NEEDS_REVIEW

    notifications = fam["parent"].get("/api/v1/parents/notifications/?unread=1")
    assert notifications.status_code == 200, notifications.content
    items = notifications.json()["results"]
    assert len(items) == 1, "same topic within 24h is reported once"
    item = items[0]
    assert item["kind"] == "difficult_topic"
    assert topic.name_ru in item["body"]
    assert item["student_nickname"] == "Алина"
    assert fam["parent"].get("/api/v1/parents/overview/").json()["unread_notifications"] == 1

    read = fam["parent"].post(f"/api/v1/parents/notifications/{item['id']}/read/")
    assert read.status_code == 200 and read.json()["updated"] == 1
    assert fam["parent"].get("/api/v1/parents/notifications/?unread=1").json()["count"] == 0


def test_weekly_report_task_is_idempotent_and_respects_opt_out():
    fam = make_family(email="w1@example.com")
    out = make_family(email="w2@example.com")
    out["parent"].patch("/api/v1/parents/settings/", {"notify_weekly_report": False}, format="json")

    assert services.generate_weekly_reports() == 1
    assert services.generate_weekly_reports() == 0
    items = fam["parent"].get("/api/v1/parents/notifications/").json()["results"]
    assert [i["kind"] for i in items] == ["weekly_report"]
    assert "не было занятий" in items[0]["body"]
    assert out["parent"].get("/api/v1/parents/notifications/").json()["count"] == 0


def test_revoking_child_data_consent_deactivates_child():
    fam = make_family()
    consents = fam["parent"].get("/api/v1/parents/consents/")
    assert consents.status_code == 200, consents.content
    child_data = next(c for c in consents.json() if c["consent_type"] == "child_data" and c["granted"])
    assert child_data["student_id"] == fam["child"]["id"]

    terms = next(c for c in consents.json() if c["consent_type"] == "terms")
    blocked = fam["parent"].post(f"/api/v1/parents/consents/{terms['id']}/revoke/")
    assert blocked.status_code == 400 and blocked.json()["error"]["code"] == "not_revocable"

    revoked = fam["parent"].post(f"/api/v1/parents/consents/{child_data['id']}/revoke/")
    assert revoked.status_code == 200, revoked.content
    assert revoked.json()["granted"] is False

    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    assert student.is_active is False
    assert fam["student"].get("/api/v1/auth/me/").status_code == 401
    assert fam["parent"].get("/api/v1/parents/children/").json() == []


def test_erase_child_data_removes_learning_history(fake_provider):  # noqa: F811
    fam = make_family()
    child_id = fam["child"]["id"]
    _start_question_session(fam["student"])
    typed = fam["student"].post(
        "/api/v1/assignments/upload/", {"source": "text", "typed_text": "2 + 2 = ?"}, format="multipart"
    )
    assert typed.status_code == 201

    erased = fam["parent"].post(f"/api/v1/parents/children/{child_id}/erase/")
    assert erased.status_code == 200, erased.content
    assert erased.json()["erased"]["sessions"] == 1
    assert erased.json()["erased"]["uploads"] == 1

    assert LearningSession.objects.filter(student_id=child_id).count() == 0
    student = StudentProfile.objects.get(pk=child_id)
    assert student.is_active is False and student.deleted_at is not None
    assert student.nickname == "Удалённый профиль"
    assert ConsentRecord.objects.filter(student=student, granted=True).count() == 0
    assert fam["student"].get("/api/v1/auth/me/").status_code == 401


def test_delete_family_requires_password_and_closes_every_account():
    fam = make_family()
    url = "/api/v1/parents/family/delete/"
    wrong = fam["parent"].post(url, {"password": "nope", "confirm": True}, format="json")
    assert wrong.status_code == 403
    unconfirmed = fam["parent"].post(url, {"password": "Strong-pass-123", "confirm": False}, format="json")
    assert unconfirmed.status_code == 400

    ok = fam["parent"].post(url, {"password": "Strong-pass-123", "confirm": True}, format="json")
    assert ok.status_code == 200, ok.content
    assert ok.json() == {"children_erased": 1}
    assert "ud_refresh" in ok.cookies and ok.cookies["ud_refresh"].value == ""

    parent_user = User.objects.get(pk=fam["parent_user"]["id"])
    assert parent_user.is_active is False and parent_user.email is None
    assert fam["parent"].get("/api/v1/parents/overview/").status_code == 401
    assert fam["student"].get("/api/v1/auth/me/").status_code == 401
    login = fam["parent"].post(
        "/api/v1/auth/login/", {"email": "parent@example.com", "password": "Strong-pass-123"}, format="json"
    )
    assert login.status_code in (400, 401)
