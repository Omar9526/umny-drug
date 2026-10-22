"""Self-check quizzes: generate (AI or arithmetic rules), answer with server-side checking, finish → progress.

Correct answers never leave the server before the child answers; after each answer the result and the
explanation for that one question are returned. Maths numeric answers are checked by the same SymPy
verifier as homework answers, so a model mistake in «correct» can only affect wording, not the verdict
on equivalent forms (0.5 == 1/2).
"""

from __future__ import annotations

import logging
import re

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from ai.base import AIProviderError, QuizRequest
from ai.costs import ensure_budget, record_usage
from ai.registry import get_provider
from ai.schemas import QuizSpec
from ai.verifiers.math import verify_math
from apps.accounts.models import StudentProfile
from apps.core.audit import audit
from apps.core.exceptions import DomainError
from apps.curriculum.models import Grade, Topic
from apps.learning.models import LearningProgress
from apps.learning.services import apply_quiz_result

from .models import Question, Quiz, QuizAttempt

logger = logging.getLogger("umnydrug.quizzes")

QUESTIONS_PER_QUIZ = 4
OPTION_KEYS = "abcd"
_WS = re.compile(r"\s+")


def normalize(text: object) -> str:
    return _WS.sub(" ", str(text).strip().lower().replace("ё", "е"))


def _request_for(topic: Topic, grade: Grade, language: str, count: int) -> QuizRequest:
    subject = topic.section.subject
    return QuizRequest(
        topic_name=topic.name(language),
        topic_description=topic.description(language),
        keywords=[str(k) for k in (topic.keywords or [])],
        subject_name=subject.name(language),
        subject_strategy=subject.strategy,
        subject_notes=subject.ai_notes or "",
        grade_number=grade.number,
        language=language,
        count=count,
    )


GENERATION_LOCK_SECONDS = 90


@transaction.atomic
def _store_quiz(
    spec: QuizSpec, *, topic: Topic, grade: Grade, language: str, source: str, model: str
) -> Quiz:
    ky = language == "ky"
    quiz = Quiz.objects.create(
        topic=topic,
        grade=grade,
        language=language,
        source=source,
        model=model[:64],
        name_ru=spec.title,
        name_ky=spec.title if ky else "",
    )
    text_key = "text_ky" if ky else "text_ru"
    rows: list[Question] = []
    for order, q in enumerate(spec.questions):
        if q.kind == "choice":
            qtype = Question.Type.SINGLE
            options = [{"key": OPTION_KEYS[i], text_key: text} for i, text in enumerate(q.options)]
            correct: object = OPTION_KEYS[q.correct_option or 0]
        elif q.kind == "number":
            qtype, options, correct = Question.Type.NUMERIC, [], q.answer.strip()
        else:
            qtype, options = Question.Type.TEXT, []
            correct = [q.answer.strip(), *[a.strip() for a in q.accepted if a.strip()]]
        localized = {"prompt_ky": q.prompt, "explanation_ky": q.explanation, "hint_ky": q.hint} if ky else {}
        rows.append(
            Question(
                quiz=quiz,
                order=order,
                type=qtype,
                prompt_ru=q.prompt,
                options=options,
                correct=correct,
                explanation_ru=q.explanation,
                hint_ru=q.hint,
                **localized,
            )
        )
    Question.objects.bulk_create(rows)
    return quiz


def _provider_error(exc: AIProviderError) -> DomainError:
    return DomainError(str(exc), code=exc.code, status_code=503 if exc.retryable else 409)


def _generate(*, student: StudentProfile, topic: Topic, grade: Grade, language: str) -> Quiz:
    provider = get_provider()
    request = _request_for(topic, grade, language, QUESTIONS_PER_QUIZ)
    try:
        if not getattr(provider, "demo_mode", False):
            ensure_budget(student=student, family=student.family)
        spec, usage = provider.generate_quiz(request)
    except AIProviderError as exc:
        if exc.usage is not None:
            record_usage(
                purpose="quiz",
                usage=exc.usage,
                provider=provider.name,
                family=student.family,
                student=student,
            )
        logger.warning("quiz generation failed: %s", exc.code, extra={"event": "ai.quiz_failed"})
        raise _provider_error(exc) from exc
    if usage.model == "rules":
        source = Quiz.Source.RULES
    else:
        source = Quiz.Source.GEMINI if provider.name == "gemini" else Quiz.Source.ANTHROPIC
        record_usage(
            purpose="quiz", usage=usage, provider=provider.name, family=student.family, student=student
        )
    return _store_quiz(spec, topic=topic, grade=grade, language=language, source=source, model=usage.model)


def start_quiz(*, student: StudentProfile, topic: Topic, request=None) -> QuizAttempt:
    """Resume an unfinished attempt on this topic, or hand out a quiz the child has not seen yet.

    The model call in ``_generate`` can take tens of seconds, so it runs outside any transaction;
    only the bookkeeping below is atomic (otherwise SQLite in dev — and long-held row locks in
    production — block every other writer for the whole generation).
    """
    if not topic.is_active or topic.section.grade.curriculum_id != student.grade.curriculum_id:
        raise DomainError("Тема недоступна.", code="not_found", status_code=404)
    existing = (
        QuizAttempt.objects.filter(student=student, quiz__topic=topic, status=QuizAttempt.Status.IN_PROGRESS)
        .select_related("quiz")
        .order_by("-started_at")
        .first()
    )
    if existing is not None:
        return existing
    language = student.explanation_language
    grade = topic.section.grade
    quiz = (
        Quiz.objects.filter(topic=topic, language=language, is_active=True)
        .exclude(source=Quiz.Source.RULES)
        .exclude(attempts__student=student)
        .order_by("?")
        .first()
    )
    if quiz is None:
        # One generation per child and topic at a time: a double tap or a second tab must not pay twice.
        lock_key = f"quiz-start:{student.pk}:{topic.pk}"
        if not cache.add(lock_key, 1, timeout=GENERATION_LOCK_SECONDS):
            raise DomainError(
                "Проверка уже готовится. Подожди несколько секунд.", code="quiz_generating", status_code=409
            )
        try:
            quiz = _generate(student=student, topic=topic, grade=grade, language=language)
        finally:
            cache.delete(lock_key)
    return _open_attempt(student=student, topic=topic, quiz=quiz, request=request)


@transaction.atomic
def _open_attempt(*, student: StudentProfile, topic: Topic, quiz: Quiz, request=None) -> QuizAttempt:
    # Serialise concurrent starts for this child and re-check: a parallel request may have opened an
    # attempt while this one was generating (the extra quiz simply stays in the pool).
    list(StudentProfile.objects.select_for_update().filter(pk=student.pk).values_list("pk", flat=True))
    existing = (
        QuizAttempt.objects.filter(student=student, quiz__topic=topic, status=QuizAttempt.Status.IN_PROGRESS)
        .select_related("quiz")
        .order_by("-started_at")
        .first()
    )
    if existing is not None:
        return existing
    attempt = QuizAttempt.objects.create(
        quiz=quiz, student=student, family=student.family, total_count=quiz.questions.count()
    )
    LearningProgress.objects.get_or_create(
        student=student,
        topic=topic,
        defaults={
            "family": student.family,
            "status": LearningProgress.Status.LEARNING,
            "last_activity_at": timezone.now(),
        },
    )
    audit(
        "quiz.started",
        actor=student.user,
        target=attempt,
        request=request,
        topic_id=topic.id,
        source=quiz.source,
    )
    return attempt


def _as_list(value: object) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(v) for v in value]
    return [str(value)]


def _check(question: Question, answer: object, lang: str) -> tuple[bool, str]:
    """Returns (correct, human-readable correct answer)."""
    kind = question.type
    if kind == Question.Type.SINGLE:
        options = {o["key"]: o["text"] for o in question.option_texts(lang)}
        key = str(question.correct)
        return normalize(answer) == normalize(key), options.get(key, key)
    if kind == Question.Type.MULTIPLE:
        options = {o["key"]: o["text"] for o in question.option_texts(lang)}
        expected = sorted(normalize(k) for k in _as_list(question.correct))
        given = sorted(normalize(k) for k in _as_list(answer))
        return given == expected, ", ".join(options.get(k, k) for k in _as_list(question.correct))
    if kind == Question.Type.NUMERIC:
        expected = str(question.correct)
        verdict = verify_math(expected, str(answer), tolerance=max(float(question.tolerance or 0), 1e-6))
        return verdict.verdict == "correct", expected
    if kind == Question.Type.TEXT:
        accepted = _as_list(question.correct)
        return normalize(answer) in {normalize(a) for a in accepted}, accepted[0] if accepted else ""
    # ordering / matching: exact sequence match
    expected_seq = _as_list(question.correct)
    return _as_list(answer) == expected_seq, ", ".join(expected_seq)


def _result_payload(attempt: QuizAttempt, question: Question) -> dict:
    result = attempt.results[str(question.id)]
    return {
        "question_id": question.id,
        "correct": result["correct"],
        "explanation": result["explanation"],
        "correct_answer": result["correct_answer"],
        "correct_keys": result.get("correct_keys", []),
        "answered": len(attempt.results),
        "total": attempt.total_count,
    }


@transaction.atomic
def answer_question(*, attempt: QuizAttempt, question_id: int, answer: object) -> dict:
    attempt = QuizAttempt.objects.select_for_update().select_related("quiz", "student").get(pk=attempt.pk)
    if attempt.status != QuizAttempt.Status.IN_PROGRESS:
        raise DomainError("Эта проверка уже завершена.", code="quiz_finished", status_code=409)
    question = attempt.quiz.questions.filter(pk=question_id).first()
    if question is None:
        raise DomainError("Вопрос не найден.", code="not_found", status_code=404)
    key = str(question.id)
    if key in attempt.results:  # idempotent: a retried request does not change the verdict
        return _result_payload(attempt, question)
    lang = attempt.student.explanation_language
    correct, correct_answer = _check(question, answer, lang)
    attempt.answers[key] = answer
    attempt.results[key] = {
        "correct": correct,
        "explanation": question.explanation(lang),
        "correct_answer": correct_answer,
        # option keys, so the client highlights the right option by key rather than by text
        "correct_keys": _as_list(question.correct)
        if question.type in (Question.Type.SINGLE, Question.Type.MULTIPLE)
        else [],
        "checked_at": timezone.now().isoformat(),
    }
    if correct:
        attempt.correct_count += 1
    attempt.save(update_fields=["answers", "results", "correct_count", "updated_at"])
    return _result_payload(attempt, question)


@transaction.atomic
def finish_quiz(*, attempt: QuizAttempt, request=None) -> QuizAttempt:
    attempt = (
        QuizAttempt.objects.select_for_update().select_related("quiz", "student__user").get(pk=attempt.pk)
    )
    if attempt.status == QuizAttempt.Status.FINISHED:
        return attempt
    attempt.status = QuizAttempt.Status.FINISHED
    attempt.finished_at = timezone.now()
    score = attempt.correct_count / attempt.total_count if attempt.total_count else 0.0
    answered = len(attempt.results)
    attempt.topics_to_review = [attempt.quiz.topic_id] if answered and score < 0.5 else []
    attempt.save(update_fields=["status", "finished_at", "topics_to_review", "updated_at"])
    if answered:  # skipping every question says nothing about the topic: leave its status alone
        apply_quiz_result(attempt, score)
    audit(
        "quiz.finished",
        actor=attempt.student.user,
        target=attempt,
        request=request,
        correct=attempt.correct_count,
        total=attempt.total_count,
    )
    return attempt
