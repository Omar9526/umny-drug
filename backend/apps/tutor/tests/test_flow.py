"""End-to-end: upload → recognition → confirm → explain (SSE) → check answer → complete → history."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.tests.helpers import make_family
from apps.assignments.models import Assignment, AssignmentUpload
from apps.learning.models import LearningProgress
from apps.tutor.models import AIUsage, LearningSession

from .fakes import fake_provider  # noqa: F401 - pytest fixture
from .helpers import parse_sse, png_bytes

pytestmark = pytest.mark.django_db

UPLOAD = "/api/v1/assignments/upload/"


def _upload_text(client, text="2 + 2 = ?"):
    response = client.post(UPLOAD, {"source": "text", "typed_text": text}, format="multipart")
    assert response.status_code == 201, response.content
    return response.json()


def test_demo_text_flow_to_completed_session():
    fam = make_family(email="a@example.com", grade=5)
    student = fam["student"]

    upload = _upload_text(student, "2 + 2 = ?")
    assert upload["status"] == "recognized"
    assert upload["demo_mode"] is True
    assert len(upload["tasks"]) == 1
    task = upload["tasks"][0]
    assert task["subject"]["slug"] == "math"

    detail = student.get(f"/api/v1/assignments/{task['id']}/").json()
    assert detail["status"] == "recognized"

    confirm = student.post(
        f"/api/v1/assignments/{task['id']}/confirm/",
        {"confirmed_text": "2 + 2 = ?", "subject_slug": "math"},
        format="json",
    )
    assert confirm.status_code == 200, confirm.content
    session_id = confirm.json()["session"]["id"]
    assert Assignment.objects.get(id=task["id"]).status == "in_progress"

    # first explanation, streamed
    stream = student.post(
        f"/api/v1/tutor/sessions/{session_id}/messages/",
        {"command": "start"},
        format="json",
        HTTP_ACCEPT="text/event-stream",  # exactly what the browser client sends
    )
    assert stream.status_code == 200
    assert stream["Content-Type"].startswith("text/event-stream")
    events = parse_sse(stream)
    kinds = [e for e, _ in events]
    assert kinds[0] == "delta" and kinds[-1] == "final"
    final = events[-1][1]
    assert "Давай разберёмся" in final["message"]["content"]
    assert final["session"]["explanations_count"] == 1

    session = student.get(f"/api/v1/tutor/sessions/{session_id}/").json()
    assert [m["role"] for m in session["messages"]] == ["assistant"]
    assert session["answer_kind"] == "number"
    assert session["check_question"]
    assert session["steps"] and session["demo_mode"] is True

    # correct answer verified by SymPy (demo computed expected 4)
    check = student.post(
        f"/api/v1/tutor/sessions/{session_id}/check-answer/", {"answer_text": "4"}, format="json"
    )
    assert check.status_code == 200, check.content
    body = check.json()
    assert body["attempt"]["verification"]["verdict"] == "correct"
    assert body["attempt"]["verification"]["method"] == "numeric"
    assert body["attempt"]["is_independent"] is True
    assert body["session"]["status"] == "completed"
    assert body["session"]["outcome"] == "independent"

    assignment = Assignment.objects.get(id=task["id"])
    assert assignment.status == "completed"
    history = student.get("/api/v1/learning/history/").json()["results"]
    assert history[0]["id"] == session_id and history[0]["outcome"] == "independent"

    # a closed session refuses further turns
    closed = parse_sse(
        student.post(f"/api/v1/tutor/sessions/{session_id}/messages/", {"command": "hint"}, format="json")
    )
    assert closed[0][0] == "error" and closed[0][1]["code"] == "session_closed"


def test_wrong_answer_then_hint_then_correct_counts_as_with_help(fake_provider):  # noqa: F811
    fam = make_family(email="a@example.com", grade=5)
    student = fam["student"]
    upload = _upload_text(student, "Реши уравнение 2x + 3 = 11")
    assert fake_provider.recognize_calls == 1
    assert len(upload["tasks"]) == 2  # scripted provider always returns two tasks
    first, second = upload["tasks"]
    assert (
        first["topic"]["slug"] in ("solve-equations", "equation-problems", "linear-equations-6")
        or first["topic"] is None
    )

    session_id = student.post(
        f"/api/v1/assignments/{first['id']}/confirm/", {"confirmed_text": first["text"]}, format="json"
    ).json()["session"]["id"]
    parse_sse(
        student.post(f"/api/v1/tutor/sessions/{session_id}/messages/", {"command": "start"}, format="json")
    )

    wrong = student.post(
        f"/api/v1/tutor/sessions/{session_id}/check-answer/", {"answer_text": "x = 5"}, format="json"
    ).json()
    assert wrong["attempt"]["verification"]["verdict"] == "incorrect"
    assert wrong["session"]["status"] == "active"

    hint = parse_sse(
        student.post(f"/api/v1/tutor/sessions/{session_id}/messages/", {"command": "hint"}, format="json")
    )
    assert hint[-1][1]["session"]["hints_used"] == 1

    right = student.post(
        f"/api/v1/tutor/sessions/{session_id}/check-answer/", {"answer_text": "x=4"}, format="json"
    ).json()
    assert right["attempt"]["verification"]["verdict"] == "correct"
    assert right["attempt"]["is_independent"] is False
    assert right["session"]["outcome"] == "with_help"

    detail = student.get(f"/api/v1/tutor/sessions/{session_id}/").json()
    assert [s["id"] for s in detail["siblings"]] == [second["id"]]
    assert detail["attempts"][0]["verification"]["verdict"] == "incorrect"
    # usage is recorded for cost monitoring
    assert AIUsage.objects.filter(purpose="tutor").count() == 2
    assert AIUsage.objects.filter(purpose="recognition").count() == 1
    session = LearningSession.objects.get(id=session_id)
    if session.topic_id:
        progress = LearningProgress.objects.get(student=session.student, topic=session.topic)
        assert progress.status == "completed"


def test_open_answer_falls_back_to_model_assessment(fake_provider):  # noqa: F811
    fam = make_family(email="a@example.com", grade=5)
    student = fam["student"]
    created = student.post(
        "/api/v1/tutor/sessions/",
        {"mode": "question", "subject_slug": "russian", "question": "Что такое подлежащее?"},
        format="json",
    )
    assert created.status_code == 201, created.content
    session_id = created.json()["id"]
    assert created.json()["title"] == "Что такое подлежащее?"
    parse_sse(
        student.post(
            f"/api/v1/tutor/sessions/{session_id}/messages/",
            {"command": "start", "content": "Что такое подлежащее?"},
            format="json",
        )
    )
    # expected_answer "4" is numeric but the child answers with words → SymPy cannot verify → model assesses
    result = student.post(
        f"/api/v1/tutor/sessions/{session_id}/check-answer/",
        {"answer_text": "это главный член предложения"},
        format="json",
    ).json()
    assert result["attempt"]["verification"]["verdict"] == "partial"
    assert fake_provider.assess_calls == 1
    assert "Подсказка" in result["message"]["content"]


def test_manual_complete_without_answer_marks_not_completed():
    fam = make_family(email="a@example.com", grade=5)
    student = fam["student"]
    session_id = student.post(
        "/api/v1/tutor/sessions/", {"mode": "explain_topic", "subject_slug": "math"}, format="json"
    ).json()["id"]
    done = student.post(f"/api/v1/tutor/sessions/{session_id}/complete/")
    assert done.status_code == 200
    assert done.json()["status"] == "abandoned" and done.json()["outcome"] == "not_completed"


def test_flag_assistant_message():
    fam = make_family(email="a@example.com", grade=5)
    student = fam["student"]
    session_id = student.post(
        "/api/v1/tutor/sessions/", {"mode": "question", "question": "2 + 2 = ?"}, format="json"
    ).json()["id"]
    final = parse_sse(
        student.post(
            f"/api/v1/tutor/sessions/{session_id}/messages/",
            {"command": "start", "content": "2 + 2 = ?"},
            format="json",
        )
    )[-1][1]
    flagged = student.post(
        f"/api/v1/tutor/sessions/{session_id}/messages/{final['message']['id']}/flag/",
        {"reason": "неверно"},
        format="json",
    )
    assert flagged.status_code == 200 and flagged.json()["flagged"] is True


def test_image_upload_validation_and_demo_unreadable():
    fam = make_family(email="a@example.com", grade=5)
    student = fam["student"]

    ok = student.post(
        UPLOAD,
        {"source": "camera", "images": [SimpleUploadedFile("hw.png", png_bytes(), content_type="image/png")]},
        format="multipart",
    )
    assert ok.status_code == 201, ok.content
    body = ok.json()
    assert body["status"] == "unreadable"  # demo provider never pretends to read photos
    assert len(body["images"]) == 1 and body["images"][0]["width"] == 320
    image_id = body["images"][0]["id"]
    served = student.get(f"/api/v1/assignments/images/{image_id}/")
    assert served.status_code == 200 and served["Content-Type"] == "image/jpeg"

    garbage = student.post(
        UPLOAD,
        {
            "source": "camera",
            "images": [SimpleUploadedFile("x.png", b"not an image", content_type="image/png")],
        },
        format="multipart",
    )
    assert garbage.status_code == 400 and garbage.json()["error"]["code"] == "corrupt"

    too_small = student.post(
        UPLOAD,
        {
            "source": "camera",
            "images": [SimpleUploadedFile("s.png", png_bytes((50, 50)), content_type="image/png")],
        },
        format="multipart",
    )
    assert too_small.json()["error"]["code"] == "too_small"

    empty = student.post(UPLOAD, {"source": "camera"}, format="multipart")
    assert empty.json()["error"]["code"] == "images_required"
    short_text = student.post(UPLOAD, {"source": "text", "typed_text": "a"}, format="multipart")
    assert short_text.json()["error"]["code"] == "text_required"


def test_family_isolation_for_uploads_images_and_sessions():
    a = make_family(email="a@example.com")
    b = make_family(email="b@example.com", nickname="Бекзат")
    upload = (
        a["student"]
        .post(
            UPLOAD,
            {
                "source": "camera",
                "images": [SimpleUploadedFile("hw.png", png_bytes(), content_type="image/png")],
            },
            format="multipart",
        )
        .json()
    )
    image_id = upload["images"][0]["id"]
    assert b["student"].get(f"/api/v1/assignments/images/{image_id}/").status_code == 404
    assert b["student"].get(f"/api/v1/assignments/uploads/{upload['id']}/").status_code == 404
    assert a["parent"].get(f"/api/v1/assignments/images/{image_id}/").status_code == 200  # same family
    assert b["parent"].get(f"/api/v1/assignments/images/{image_id}/").status_code == 404

    session_id = (
        a["student"]
        .post("/api/v1/tutor/sessions/", {"mode": "question", "question": "Помоги"}, format="json")
        .json()["id"]
    )
    assert b["student"].get(f"/api/v1/tutor/sessions/{session_id}/").status_code == 404
    assert (
        b["student"]
        .post(f"/api/v1/tutor/sessions/{session_id}/check-answer/", {"answer_text": "4"}, format="json")
        .status_code
        == 404
    )
    assert a["parent"].get(f"/api/v1/tutor/sessions/{session_id}/").status_code == 403


def test_purge_expired_images_deletes_files():
    from django.utils import timezone

    from apps.assignments.models import AssignmentImage
    from apps.assignments.tasks import purge_expired_images

    fam = make_family(email="a@example.com")
    fam["student"].post(
        UPLOAD,
        {"source": "camera", "images": [SimpleUploadedFile("hw.png", png_bytes(), content_type="image/png")]},
        format="multipart",
    )
    image = AssignmentImage.objects.get()
    storage, name = image.file.storage, image.file.name
    assert storage.exists(name)
    AssignmentImage.objects.filter(id=image.id).update(expires_at=timezone.now())
    assert purge_expired_images() == 1
    image.refresh_from_db()
    assert image.purged_at is not None and not storage.exists(name)
    assert AssignmentUpload.objects.get().images.count() == 1  # row kept for history
