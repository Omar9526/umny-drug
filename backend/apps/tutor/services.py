"""Tutoring session use-cases: create, stream a turn, check an answer, complete.

Concurrency model: a session row is locked (``select_for_update``) for every write that touches
counters or status, and the status is re-checked under the lock. Streaming itself happens outside
any transaction; only the short persistence step at the end is transactional.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ai.base import AIProviderError, TutorContext
from ai.costs import ensure_budget, record_usage
from ai.registry import get_provider
from ai.verifiers.math import verify_math
from apps.accounts.models import StudentProfile
from apps.core.audit import audit
from apps.core.exceptions import DomainError
from apps.core.sse import sse_event
from apps.learning.models import AnswerAttempt, VerificationResult
from apps.learning.services import apply_session_result, mark_topic_learning

from .models import AIConversation, AIMessage, LearningSession, SolutionStep

logger = logging.getLogger("umnydrug.tutor")

QUICK_COMMANDS = frozenset(
    {"start", "simpler", "example", "why", "hint", "repeat", "dont_understand", "similar", "next_step", ""}
)
# Commands that make the eventual answer «with help» even without an explicit hint.
HELP_COMMANDS = frozenset({"hint", "example", "similar"})
MAX_USER_MESSAGE = 2000
MAX_ANSWER = 2000

FEEDBACK = {
    "ru": {
        "correct": "Верно! Ты решил это сам — отличная работа. 🎉",
        "correct_help": "Верно! С подсказками, но ты довёл дело до конца. 👍",
        "correct_step": "Верно! Идём дальше.",
        "incorrect": "Пока не сходится. Проверь вычисления ещё раз: где могла закрасться ошибка?",
        "partial": "Почти! Часть ответа верная, но что-то упущено. Перечитай условие.",
        "uncertain": "Я не смог проверить этот ответ уверенно. Давай разберём его вместе: напиши, как ты рассуждал.",  # noqa: E501
    },
    "ky": {
        "correct": "Туура! Өзүң чечтиң — сонун иш. 🎉",
        "correct_help": "Туура! Кеңештер менен болсо да, аягына чыктың. 👍",
        "correct_step": "Туура! Андан ары.",
        "incorrect": "Азырынча туура келбейт. Эсептөөлөрдү дагы бир жолу текшер: ката кайсы жерде болушу мүмкүн?",  # noqa: E501
        "partial": "Дээрлик туура! Жооптун бир бөлүгү туура, бирок бир нерсе калып калды. Шартты кайра оку.",
        "uncertain": "Бул жоопту так текшере албадым. Чогуу карап көрөлү: кантип ойлонгонуңду жаз.",
    },
}


class SessionClosed(DomainError):
    status_code = 409
    default_code = "session_closed"
    default_detail = "Это занятие уже завершено. Начни новое."


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@transaction.atomic
def create_session(
    *,
    student: StudentProfile,
    mode: str,
    assignment=None,
    subject=None,
    topic=None,
    question: str = "",
    request=None,
) -> LearningSession:
    from apps.assignments.models import Assignment

    language = student.explanation_language
    if assignment is not None:
        subject = subject or assignment.subject
        topic = topic or assignment.topic
    if topic is not None and subject is None:
        subject = topic.section.subject

    if assignment is not None and assignment.label:
        title = assignment.label
    elif topic is not None:
        title = topic.name(language)
    elif assignment is not None:
        snippet = " ".join(assignment.text.split())
        title = snippet if len(snippet) <= 48 else snippet[:45] + "…"
    elif question:
        title = question.strip()[:60]
    elif subject is not None:
        title = subject.name(language)
    else:
        title = dict(LearningSession.Mode.choices).get(mode, "")

    provider = get_provider()
    session = LearningSession.objects.create(
        student=student,
        family=student.family,
        assignment=assignment,
        grade=student.grade,
        subject=subject,
        topic=topic,
        mode=mode,
        language=language,
        title=title,
    )
    AIConversation.objects.create(
        session=session,
        provider=provider.name,
        model="demo" if provider.demo_mode else settings.AI_MODEL_TUTOR,
        demo_mode=provider.demo_mode,
    )
    if assignment is not None:
        assignment.status = Assignment.Status.IN_PROGRESS
        assignment.save(update_fields=["status", "updated_at"])
    mark_topic_learning(session)
    audit("session.created", actor=student.user, target=session, request=request, mode=mode)
    return session


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------
def _history(session: LearningSession) -> list[dict]:
    messages = list(
        session.conversation.messages.filter(
            role__in=[AIMessage.Role.USER, AIMessage.Role.ASSISTANT]
        ).order_by("-created_at")[: settings.AI_HISTORY_TURNS]
    )
    messages.reverse()
    history: list[dict] = []
    for message in messages:
        entry = {"role": message.role, "content": message.content}
        if message.role == AIMessage.Role.ASSISTANT:
            payload = message.payload or {}
            tail = {
                k: payload.get(k)
                for k in ("check_question", "expected_answer", "answer_kind")
                if payload.get(k)
            }
            if tail:
                entry["content"] = f"{message.content}\n<meta>{json.dumps(tail, ensure_ascii=False)}</meta>"
                entry["check_question"] = payload.get("check_question", "")
        history.append(entry)
    while history and history[0]["role"] != "user":  # the API requires a user message first
        history.pop(0)
    return history


def build_context(session: LearningSession) -> TutorContext:
    student = session.student
    subject = session.subject
    attempts = [
        {"answer": a.answer_text, "verdict": getattr(getattr(a, "verification", None), "verdict", "")}
        for a in session.attempts.select_related("verification").order_by("attempt_number")
    ]
    return TutorContext(
        grade_number=session.grade.number,
        stage=session.grade.stage,
        language=session.language,
        mode=session.mode,
        student_nickname=student.nickname,
        subject_slug=subject.slug if subject else None,
        subject_name=subject.name(session.language) if subject else None,
        subject_strategy=subject.strategy if subject else None,
        subject_notes=subject.ai_notes if subject else "",
        topic_name=session.topic.name(session.language) if session.topic_id else None,
        assignment_text=session.assignment.text if session.assignment_id else None,
        history=_history(session),
        hints_used=session.hints_used,
        attempts=attempts,
        solution_revealed=session.solution_revealed,
    )


def _last_assistant_payload(session: LearningSession) -> dict:
    message = (
        session.conversation.messages.filter(role=AIMessage.Role.ASSISTANT)
        .exclude(command="check")
        .order_by("-created_at")
        .first()
    )
    return (message.payload or {}) if message else {}


def _answer_revealed(expected: str | None, message: str) -> bool:
    """Server-side check that the explanation itself did not hand out the expected answer."""
    if not expected:
        return False
    token = expected.strip()
    if not token:
        return False
    if len(token) < 2:
        return re.search(rf"=\s*{re.escape(token)}(?![\d.,])", message) is not None
    return re.search(rf"(?<![\w.]){re.escape(token)}(?![\w.])", message) is not None


# ---------------------------------------------------------------------------
# Turn (streamed)
# ---------------------------------------------------------------------------
def run_turn(*, session: LearningSession, command: str, content: str, request=None) -> Iterator[bytes]:
    """Generate SSE events for one tutor turn.

    Order matters: budget → context (without the new message) → persist the user message → stream →
    persist the assistant message and counters under a row lock. Errors become an ``error`` event.
    """
    command = command if command in QUICK_COMMANDS else ""
    content = (content or "").strip()[:MAX_USER_MESSAGE]
    if session.status != LearningSession.Status.ACTIVE:
        yield sse_event({"code": "session_closed", "message": SessionClosed.default_detail}, event="error")
        return
    if not content and command == "":
        yield sse_event(
            {"code": "validation_error", "message": "Напиши вопрос или выбери действие."}, event="error"
        )
        return

    provider = get_provider()
    try:
        ensure_budget(student=session.student, family=session.family)
    except AIProviderError as exc:
        yield sse_event({"code": exc.code, "message": str(exc), "retryable": False}, event="error")
        return

    context = build_context(session)  # built *before* saving the new message, so it is not duplicated
    conversation = session.conversation
    if content or command != "start":
        last = conversation.messages.order_by("-created_at").first()
        duplicate = (
            last is not None
            and last.role == AIMessage.Role.USER
            and last.command == command
            and last.content == (content or command)
        )
        if not duplicate:  # a retry after a failed turn re-sends the same message
            AIMessage.objects.create(
                conversation=conversation,
                role=AIMessage.Role.USER,
                command=command,
                content=content or command,
            )

    started = time.monotonic()
    final = None
    usage = None
    stream = provider.respond(context, command, content)
    try:
        for chunk in stream:
            if chunk.reset:
                yield sse_event({}, event="reset")
            if chunk.text:
                yield sse_event({"text": chunk.text}, event="delta")
            if chunk.final is not None:
                final = chunk.final
                usage = chunk.usage
    except GeneratorExit:
        stream.close()  # client went away: stop pulling tokens from the provider
        raise
    except AIProviderError as exc:
        if exc.usage is not None:
            _record(exc.usage, provider, session, "tutor")
        logger.warning("tutor turn failed: %s", exc.code, extra={"event": "ai.turn_failed"})
        yield sse_event({"code": exc.code, "message": str(exc), "retryable": exc.retryable}, event="error")
        return
    except Exception:
        logger.exception("tutor turn crashed", extra={"event": "ai.turn_crashed"})
        yield sse_event(
            {"code": "server_error", "message": "Что-то пошло не так. Попробуй ещё раз."}, event="error"
        )
        return

    if final is None:
        yield sse_event({"code": "empty", "message": "Помощник не ответил. Попробуй ещё раз."}, event="error")
        return

    payload = final.model_dump(exclude={"message"})
    with transaction.atomic():
        locked = LearningSession.objects.select_for_update().get(pk=session.pk)
        message = AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.ASSISTANT,
            command=command,
            content=final.message,
            payload=payload,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            latency_ms=usage.latency_ms if usage else int((time.monotonic() - started) * 1000),
        )
        if final.steps:
            base = locked.steps.count()
            SolutionStep.objects.bulk_create(
                [
                    SolutionStep(
                        session=locked,
                        order=base + i,
                        title=step.title,
                        content=step.content,
                        is_hint=(command == "hint"),
                    )
                    for i, step in enumerate(final.steps)
                ]
            )
        if locked.status == LearningSession.Status.ACTIVE:
            locked.explanations_count += 1
            if command in HELP_COMMANDS:
                locked.hints_used += 1
            if final.reveals_solution or _answer_revealed(final.expected_answer, final.message):
                locked.solution_revealed = True
            locked.last_activity_at = timezone.now()
            locked.save(
                update_fields=[
                    "explanations_count",
                    "hints_used",
                    "solution_revealed",
                    "last_activity_at",
                    "updated_at",
                ]
            )
        if usage is not None:
            _record(usage, provider, locked, "tutor")
    session.refresh_from_db()

    from .serializers import AIMessageSerializer, SessionStateSerializer

    yield sse_event(
        {"message": AIMessageSerializer(message).data, "session": SessionStateSerializer(session).data},
        event="final",
    )


def _record(usage, provider, session: LearningSession, purpose: str) -> None:
    record_usage(
        purpose=purpose,
        usage=usage,
        provider=provider.name,
        family=session.family,
        student=session.student,
        session=session,
    )
    AIConversation.objects.filter(session=session).update(
        input_tokens=F("input_tokens") + usage.input_tokens,
        output_tokens=F("output_tokens") + usage.output_tokens,
        cost_usd=F("cost_usd") + usage.cost_usd,
    )


# ---------------------------------------------------------------------------
# Answer check
# ---------------------------------------------------------------------------
def check_answer(*, session: LearningSession, answer_text: str, request=None) -> dict:
    if session.status != LearningSession.Status.ACTIVE:
        raise SessionClosed()
    answer_text = (answer_text or "").strip()[:MAX_ANSWER]
    if not answer_text:
        raise DomainError("Напиши ответ, который хочешь проверить.", code="validation_error", status_code=400)

    language = session.language if session.language in FEEDBACK else "ru"
    payload = _last_assistant_payload(session)
    expected = payload.get("expected_answer")
    kind = payload.get("answer_kind") or "none"
    rubric = payload.get("rubric") or []
    is_final = payload.get("is_final_answer", True) is not False
    provider = get_provider()

    verdict = "uncertain"
    confidence = 0.0
    method = VerificationResult.Method.MODEL
    details: dict = {}
    feedback = ""
    usage = None
    next_hint = ""

    if expected and kind in ("number", "expression"):
        result = verify_math(str(expected), answer_text)
        details = {"expected": expected, **result.details}
        if result.verdict != "uncertain":
            verdict, confidence = result.verdict, result.confidence
            method = (
                VerificationResult.Method.NUMERIC
                if details.get("method") == "numeric"
                else VerificationResult.Method.SYMPY
            )

    if verdict == "uncertain":
        if provider.demo_mode:
            method = VerificationResult.Method.DEMO
            feedback = FEEDBACK[language]["uncertain"]
        else:
            try:
                ensure_budget(student=session.student, family=session.family)
                assessment, usage = provider.assess(build_context(session), answer_text, rubric, expected)
                verdict, confidence = assessment.verdict, assessment.confidence
                feedback = assessment.feedback
                next_hint = assessment.next_hint
                details = {**details, "criteria": assessment.criteria}
                method = VerificationResult.Method.RUBRIC if rubric else VerificationResult.Method.MODEL
            except AIProviderError as exc:
                if exc.usage is not None:
                    usage = exc.usage
                logger.warning("assessment failed: %s", exc.code, extra={"event": "ai.assess_failed"})
                feedback = FEEDBACK[language]["uncertain"]
                details = {**details, "assess_error": exc.code}

    with transaction.atomic():
        # Row lock: parallel checks on one session must not share an attempt number or lose counters.
        session = (
            LearningSession.objects.select_for_update()
            .select_related("student__user", "family", "assignment")
            .get(pk=session.pk)
        )
        if session.status != LearningSession.Status.ACTIVE:
            raise SessionClosed()
        independent_before = session.hints_used == 0 and not session.solution_revealed
        if not feedback:
            if verdict == "correct":
                key = "correct" if independent_before else "correct_help"
                feedback = FEEDBACK[language][key if is_final else "correct_step"]
            else:
                feedback = FEEDBACK[language].get(verdict, FEEDBACK[language]["uncertain"])

        attempt = AnswerAttempt.objects.create(
            session=session,
            assignment=session.assignment,
            student=session.student,
            family=session.family,
            attempt_number=session.attempts_count + 1,
            answer_text=answer_text,
            hints_before=session.hints_used,
            is_independent=independent_before,
        )
        VerificationResult.objects.create(
            attempt=attempt,
            method=method,
            verdict=verdict,
            confidence=confidence,
            feedback=feedback,
            details=details,
            provider=provider.name,
            model=usage.model if usage else "",
            cost_usd=usage.cost_usd if usage else 0,
        )
        AIMessage.objects.create(
            conversation=session.conversation, role=AIMessage.Role.USER, command="check", content=answer_text
        )
        assistant = AIMessage.objects.create(
            conversation=session.conversation,
            role=AIMessage.Role.ASSISTANT,
            command="check",
            content=feedback
            + (f"\n\n**Подсказка:** {next_hint}" if next_hint and verdict != "correct" else ""),
            payload={"verdict": verdict, "confidence": confidence, "method": method, "next_hint": next_hint},
        )
        session.attempts_count += 1
        if verdict == "correct":
            session.correct_attempts += 1
        session.last_activity_at = timezone.now()
        session.save(update_fields=["attempts_count", "correct_attempts", "last_activity_at", "updated_at"])
        if usage is not None:
            _record(usage, provider, session, "assess")
        audit(
            "answer.checked",
            actor=session.student.user,
            target=session,
            request=request,
            verdict=verdict,
            method=method,
        )

    completed = False
    if verdict == "correct" and is_final:
        complete_session(session=session, request=request, reason="correct_answer")
        completed = True
    session.refresh_from_db()

    from .serializers import AIMessageSerializer, AnswerAttemptSerializer, SessionStateSerializer

    return {
        "attempt": AnswerAttemptSerializer(attempt).data,
        "message": AIMessageSerializer(assistant).data,
        "session": SessionStateSerializer(session).data,
        # A correct intermediate step: the client continues the walk-through automatically.
        "continue_with": "next_step" if verdict == "correct" and not completed else None,
    }


# ---------------------------------------------------------------------------
# Complete / flag
# ---------------------------------------------------------------------------
@transaction.atomic
def complete_session(*, session: LearningSession, request=None, reason: str = "manual") -> LearningSession:
    from apps.assignments.models import Assignment

    session = (
        LearningSession.objects.select_for_update()
        .select_related("student__user", "assignment")
        .get(pk=session.pk)
    )
    if session.status != LearningSession.Status.ACTIVE:
        return session
    if session.correct_attempts > 0:
        session.status = LearningSession.Status.COMPLETED
        session.outcome = (
            LearningSession.Outcome.UNDERSTOOD_INDEPENDENTLY
            if session.attempts.filter(is_independent=True, verification__verdict="correct").exists()
            else LearningSession.Outcome.COMPLETED_WITH_HELP
        )
    elif session.solution_revealed or session.attempts_count > 0:
        session.status = LearningSession.Status.COMPLETED
        session.outcome = LearningSession.Outcome.NEEDS_REVIEW
    else:
        session.status = LearningSession.Status.ABANDONED
        session.outcome = LearningSession.Outcome.NOT_COMPLETED

    session.understood_points = list(session.steps.order_by("order").values_list("title", flat=True)[:6])
    wrong = session.attempts.filter(verification__verdict__in=["incorrect", "partial"]).count()
    session.mistakes_fixed = [f"Исправлено ошибок: {wrong}"] if wrong and session.correct_attempts else []
    session.summary_for_parent = _parent_summary(session)
    session.ended_at = timezone.now()
    session.last_activity_at = session.ended_at
    session.save()

    if session.assignment_id:
        assignment = session.assignment
        assignment.status = {
            LearningSession.Outcome.UNDERSTOOD_INDEPENDENTLY: Assignment.Status.COMPLETED,
            LearningSession.Outcome.COMPLETED_WITH_HELP: Assignment.Status.COMPLETED,
            LearningSession.Outcome.NEEDS_REVIEW: Assignment.Status.NEEDS_REVIEW,
            LearningSession.Outcome.NOT_COMPLETED: Assignment.Status.ABANDONED,
        }[session.outcome]
        if assignment.status == Assignment.Status.COMPLETED:
            assignment.completed_at = session.ended_at
        assignment.save(update_fields=["status", "completed_at", "updated_at"])

    apply_session_result(session)
    from apps.parents.services import notify_session_outcome

    notify_session_outcome(session)
    audit(
        "session.completed",
        actor=session.student.user,
        target=session,
        request=request,
        outcome=session.outcome,
        reason=reason,
    )
    return session


def _parent_summary(session: LearningSession) -> str:
    subject = session.subject.name_ru if session.subject_id else "предмет не определён"
    topic = f", тема «{session.topic.name_ru}»" if session.topic_id else ""
    outcome = {
        LearningSession.Outcome.UNDERSTOOD_INDEPENDENTLY: "решено самостоятельно, без подсказок",
        LearningSession.Outcome.COMPLETED_WITH_HELP: f"выполнено с подсказками ({session.hints_used})",
        LearningSession.Outcome.NEEDS_REVIEW: "самостоятельно не получилось, тему стоит повторить",
        LearningSession.Outcome.NOT_COMPLETED: "не доведено до конца",
    }.get(session.outcome, "")
    return f"{subject}{topic}: {outcome}. Попыток: {session.attempts_count}."


@transaction.atomic
def flag_message(*, session: LearningSession, message_id, reason: str, request=None) -> AIMessage:
    message = session.conversation.messages.filter(id=message_id, role=AIMessage.Role.ASSISTANT).first()
    if message is None:
        raise DomainError("Сообщение не найдено.", code="not_found", status_code=404)
    message.flagged = True
    message.flag_reason = (reason or "")[:255]
    message.save(update_fields=["flagged", "flag_reason"])
    audit("message.flagged", actor=session.student.user, target=message, request=request)
    return message
