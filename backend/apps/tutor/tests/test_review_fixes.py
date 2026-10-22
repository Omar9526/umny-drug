"""Regression tests for the stage-2 review findings."""

from __future__ import annotations

import time

import pytest
from django.test import override_settings

from apps.accounts.tests.helpers import make_family
from apps.tutor.models import AIUsage, LearningSession

from .fakes import ScriptedProvider, fake_provider  # noqa: F401 - fixture
from .helpers import parse_sse

pytestmark = pytest.mark.django_db


def _start_session(student, question="12 * 4 = ?"):
    created = student.post(
        "/api/v1/tutor/sessions/", {"mode": "question", "question": question}, format="json"
    )
    assert created.status_code == 201, created.content
    session_id = created.json()["id"]
    parse_sse(
        student.post(
            f"/api/v1/tutor/sessions/{session_id}/messages/",
            {"command": "start", "content": question},
            format="json",
        )
    )
    return session_id


def test_expected_answer_never_reaches_the_client():
    fam = make_family(email="a@example.com")
    student = fam["student"]
    session_id = _start_session(student)

    detail = student.get(f"/api/v1/tutor/sessions/{session_id}/")
    body = detail.content.decode("utf-8")
    assert "expected_answer" not in body and "rubric" not in body
    assert detail.json()["answer_kind"] == "number"  # the harmless parts are still there

    final = parse_sse(
        student.post(f"/api/v1/tutor/sessions/{session_id}/messages/", {"command": "hint"}, format="json")
    )[-1]
    assert "expected_answer" not in final[1]["message"]["payload"]


@pytest.mark.parametrize(
    "payload",
    ["9^9^9", "factorial(10^7)", "print(2)", "open(0)", "x.subs(1)", "__import__('os')", "2**2**2**2"],
)
def test_math_verifier_refuses_dangerous_input_quickly(payload):
    from ai.verifiers.math import verify_math

    started = time.monotonic()
    verdict = verify_math("5", payload)
    assert verdict.verdict == "uncertain"
    assert time.monotonic() - started < 3.5


@pytest.mark.parametrize(
    ("expected", "given", "verdict"),
    [
        ("2*x = 8", "x = 4", "correct"),
        ("2*x = 8", "4", "correct"),
        ("2*x = 8", "x = 8", "incorrect"),
        ("2*x = 8", "3x = 8", "incorrect"),
        ("x=2; x=-2", "2; -2", "correct"),
        ("x=2; x=-2", "-2", "incorrect"),
        ("1000000", "1000001", "incorrect"),
        ("35", "5 или 7", "incorrect"),
        ("6", "2 3", "uncertain"),
        ("5", "5m", "correct"),
        ("5", "5 м", "correct"),
        ("4", "4,0", "correct"),
        ("0.75", "3/4", "correct"),
        ("x**2 - 4", "(x-2)(x+2)", "correct"),
    ],
)
def test_math_verifier_equations_sets_and_units(expected, given, verdict):
    from ai.verifiers.math import verify_math

    assert verify_math(expected, given).verdict == verdict


@override_settings(AI_DAILY_BUDGET_PER_FAMILY_USD=0.0001)
def test_family_budget_stops_further_ai_calls(fake_provider):  # noqa: F811
    from ai.base import Usage

    fake_provider.respond_usage = Usage(input_tokens=10, output_tokens=10, cost_usd=0.5, model="fake")
    fam = make_family(email="a@example.com")
    student = fam["student"]
    session_id = _start_session(student)
    assert AIUsage.objects.filter(family__isnull=False).exists()

    events = parse_sse(
        student.post(f"/api/v1/tutor/sessions/{session_id}/messages/", {"command": "hint"}, format="json")
    )
    assert events[-1][0] == "error" and events[-1][1]["code"] == "family_budget_exceeded"


def test_intermediate_correct_answer_does_not_complete_session(fake_provider):  # noqa: F811
    fake_provider.final_answer = False
    fam = make_family(email="a@example.com")
    student = fam["student"]
    session_id = _start_session(student, "Реши 2x + 3 = 11")
    result = student.post(
        f"/api/v1/tutor/sessions/{session_id}/check-answer/", {"answer_text": "4"}, format="json"
    ).json()
    assert result["attempt"]["verification"]["verdict"] == "correct"
    assert result["session"]["status"] == "active"
    assert result["continue_with"] == "next_step"
    assert "Идём дальше" in result["message"]["content"]


def test_retry_after_error_does_not_duplicate_user_message(fake_provider):  # noqa: F811
    fam = make_family(email="a@example.com")
    student = fam["student"]
    session_id = _start_session(student)
    fake_provider.fail_next = True
    first = parse_sse(
        student.post(f"/api/v1/tutor/sessions/{session_id}/messages/", {"content": "почему?"}, format="json")
    )
    assert first[-1][0] == "error"
    second = parse_sse(
        student.post(f"/api/v1/tutor/sessions/{session_id}/messages/", {"content": "почему?"}, format="json")
    )
    assert second[-1][0] == "final"
    messages = student.get(f"/api/v1/tutor/sessions/{session_id}/").json()["messages"]
    assert [m["content"] for m in messages if m["role"] == "user"].count("почему?") == 1


def test_reconfirm_with_new_text_closes_previous_session():
    fam = make_family(email="a@example.com")
    student = fam["student"]
    upload = student.post(
        "/api/v1/assignments/upload/", {"source": "text", "typed_text": "2 + 2 = ?"}, format="multipart"
    ).json()
    task_id = upload["tasks"][0]["id"]
    first = student.post(
        f"/api/v1/assignments/{task_id}/confirm/", {"confirmed_text": "2 + 2 = ?"}, format="json"
    ).json()["session"]["id"]
    second = student.post(
        f"/api/v1/assignments/{task_id}/confirm/", {"confirmed_text": "2 + 3 = ?"}, format="json"
    ).json()["session"]["id"]
    assert first != second
    assert LearningSession.objects.get(id=first).status == "abandoned"
    assert LearningSession.objects.get(id=second).status == "active"
    # the auto-detected subject can be removed explicitly
    cleared = student.post(
        f"/api/v1/assignments/{task_id}/confirm/",
        {"confirmed_text": "2 + 3 = ?", "subject_slug": None},
        format="json",
    ).json()
    assert cleared["assignment"]["subject"] is None


def test_scripted_provider_defaults():
    provider = ScriptedProvider()
    assert provider.final_answer is True and provider.fail_next is False
