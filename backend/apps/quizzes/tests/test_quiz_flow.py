"""Self-check quizzes: generation (rules / AI), server-side checking, progress effects, isolation."""

from __future__ import annotations

import pytest

from apps.accounts.models import StudentProfile
from apps.accounts.tests.helpers import make_family
from apps.curriculum.models import Topic
from apps.learning.models import LearningProgress
from apps.quizzes.models import Question, Quiz, QuizAttempt
from apps.tutor.models import AIUsage
from apps.tutor.tests.fakes import fake_provider  # noqa: F401 - fixture

pytestmark = pytest.mark.django_db

START = "/api/v1/quizzes/start/"


def _topic(subject: str = "math", grade: int = 5) -> Topic:
    topic = (
        Topic.objects.filter(section__subject__slug=subject, section__grade__number=grade)
        .order_by("id")
        .first()
    )
    assert topic is not None, "seeded curriculum expected"
    return topic


def _start(client, topic: Topic):
    response = client.post(START, {"topic_id": topic.id}, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def _answer(client, attempt_id: str, question_id: int, answer):
    return client.post(
        f"/api/v1/quizzes/attempts/{attempt_id}/answer/",
        {"question_id": question_id, "answer": answer},
        format="json",
    )


def _correct_answer(question_id: int) -> str:
    question = Question.objects.get(pk=question_id)
    correct = question.correct
    return correct[0] if isinstance(correct, list) else str(correct)


def _wrong_answer(question_id: int) -> str:
    question = Question.objects.get(pk=question_id)
    if question.type == Question.Type.SINGLE:
        keys = [o["key"] for o in question.options]
        return next(k for k in keys if k != question.correct)
    return "-999"


def test_math_quiz_in_demo_mode_is_real_arithmetic_and_hides_answers():
    fam = make_family()
    topic = _topic()
    body = _start(fam["student"], topic)
    assert body["status"] == "in_progress"
    assert body["quiz"]["source"] == "rules"
    assert body["total_count"] == len(body["questions"]) == 4
    assert body["topic"] == {
        "id": topic.id,
        "name": topic.name_ru,
        "subject": {
            "id": topic.section.subject_id,
            "slug": "math",
            "name": "Математика",
            "icon": topic.section.subject.icon,
            "color": topic.section.subject.color,
        },
    }
    for question in body["questions"]:
        assert set(question) == {"id", "order", "type", "prompt", "options", "hint"}
        for option in question["options"]:
            assert set(option) == {"key", "text"}
    assert LearningProgress.objects.get(student_id=fam["child"]["id"], topic=topic).status == "learning"

    for question in body["questions"]:
        res = _answer(fam["student"], body["id"], question["id"], _correct_answer(question["id"]))
        assert res.status_code == 200, res.content
        payload = res.json()
        assert payload["correct"] is True
        assert payload["explanation"]
        assert payload["correct_answer"]
    # answering the same question again does not change anything
    first = body["questions"][0]
    again = _answer(fam["student"], body["id"], first["id"], "0").json()
    assert again["correct"] is True and again["answered"] == 4

    finished = fam["student"].post(f"/api/v1/quizzes/attempts/{body['id']}/finish/")
    assert finished.status_code == 200, finished.content
    result = finished.json()
    assert (result["status"], result["correct_count"], result["score"]) == ("finished", 4, 1.0)
    assert result["progress_status"] == "completed"
    assert result["topics_to_review"] == []
    assert AIUsage.objects.filter(purpose="quiz").count() == 0, "rule-based quizzes cost nothing"

    # a second perfect quiz on a completed topic → mastered
    second = _start(fam["student"], topic)
    assert second["id"] != body["id"]
    for question in second["questions"]:
        _answer(fam["student"], second["id"], question["id"], _correct_answer(question["id"]))
    result = fam["student"].post(f"/api/v1/quizzes/attempts/{second['id']}/finish/").json()
    assert result["progress_status"] == "mastered"


def test_numeric_answers_accept_equivalent_forms():
    fam = make_family()
    body = _start(fam["student"], _topic())
    numeric = next((q for q in body["questions"] if q["type"] == "numeric"), None)
    if numeric is None:
        pytest.skip("rules picked no numeric question for this topic")
    expected = int(_correct_answer(numeric["id"]))
    res = _answer(fam["student"], body["id"], numeric["id"], f" {expected}.0 ")
    assert res.json()["correct"] is True


def test_wrong_answers_send_topic_to_review():
    fam = make_family()
    topic = _topic()
    body = _start(fam["student"], topic)
    for question in body["questions"]:
        res = _answer(fam["student"], body["id"], question["id"], _wrong_answer(question["id"]))
        assert res.json()["correct"] is False
    result = fam["student"].post(f"/api/v1/quizzes/attempts/{body['id']}/finish/").json()
    assert result["correct_count"] == 0
    assert result["progress_status"] == "needs_review"
    assert result["topics_to_review"] == [topic.id]
    assert LearningProgress.objects.get(student_id=fam["child"]["id"], topic=topic).status == "needs_review"


def test_unfinished_attempt_is_resumed_and_finished_attempt_is_closed():
    fam = make_family()
    topic = _topic()
    first = _start(fam["student"], topic)
    assert _start(fam["student"], topic)["id"] == first["id"]
    fam["student"].post(f"/api/v1/quizzes/attempts/{first['id']}/finish/")
    late = _answer(fam["student"], first["id"], first["questions"][0]["id"], "1")
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "quiz_finished"
    empty = _answer(fam["student"], first["id"], first["questions"][0]["id"], "   ")
    assert empty.status_code == 400


def test_non_math_topic_needs_the_ai_provider_in_demo_mode():
    fam = make_family()
    response = fam["student"].post(START, {"topic_id": _topic("russian", 5).id}, format="json")
    assert response.status_code == 409, response.content
    assert response.json()["error"]["code"] == "demo_mode"
    assert QuizAttempt.objects.count() == 0


def test_ai_quiz_is_generated_once_and_shared_between_children(fake_provider):  # noqa: F811
    a = make_family(email="a@example.com")
    b = make_family(email="b@example.com")
    topic = _topic("russian", 5)
    first = _start(a["student"], topic)
    assert first["quiz"]["source"] == "anthropic"
    assert [q["type"] for q in first["questions"]] == ["single", "numeric", "text"]
    assert fake_provider.quiz_calls == 1
    assert AIUsage.objects.filter(purpose="quiz").count() == 1

    second = _start(b["student"], topic)
    assert second["quiz"]["id"] == first["quiz"]["id"], "an unseen quiz is reused, not regenerated"
    assert fake_provider.quiz_calls == 1

    text_question = next(q for q in second["questions"] if q["type"] == "text")
    assert _answer(b["student"], second["id"], text_question["id"], "СУММА ").json()["correct"] is True
    single = next(q for q in second["questions"] if q["type"] == "single")
    assert _answer(b["student"], second["id"], single["id"], "b").json()["correct"] is False

    # the same child asks again after finishing → a fresh quiz is generated
    a["student"].post(f"/api/v1/quizzes/attempts/{first['id']}/finish/")
    third = _start(a["student"], topic)
    assert third["quiz"]["id"] != first["quiz"]["id"]
    assert fake_provider.quiz_calls == 2
    assert Quiz.objects.filter(topic=topic).count() == 2


def test_attempts_are_private_to_the_student():
    a = make_family(email="a@example.com")
    b = make_family(email="b@example.com")
    body = _start(a["student"], _topic())
    url = f"/api/v1/quizzes/attempts/{body['id']}/"
    assert b["student"].get(url).status_code == 404
    assert b["student"].post(url + "finish/").status_code == 404
    assert a["parent"].get(url).status_code == 403
    assert a["parent"].post(START, {"topic_id": _topic().id}, format="json").status_code == 403
    student = StudentProfile.objects.get(pk=a["child"]["id"])
    assert QuizAttempt.objects.filter(student=student).count() == 1
