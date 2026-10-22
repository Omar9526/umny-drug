"""Explicitly marked Demo provider.

Used only when no AI key is configured (and in tests). It never pretends to understand a photo:
image recognition is reported as unreadable with a clear reason, typed text is split into tasks,
and tutoring turns are templated walk-throughs that say they are demo content.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from .base import AIProviderError, ImageInput, QuizRequest, StreamChunk, SubjectOption, TutorContext, Usage
from .quiz_rules import build_math_quiz
from .schemas import AssessmentResult, QuizSpec, RecognitionResult, RecognizedTask, TutorStep, TutorTurn

DEMO_NOTE = {
    "ru": "Демо-режим: AI-провайдер не подключён, это учебный шаблон, а не настоящий разбор.",
    "ky": "Демо-режим: AI туташтырылган эмес, бул окуу үлгүсү, чыныгы түшүндүрмө эмес.",
}

_SIMPLE_EQUATION = re.compile(r"^\s*(\d+)\s*([+\-*/])\s*(\d+)\s*=?\s*\??\s*$")


def _note(lang: str) -> str:
    return DEMO_NOTE.get(lang, DEMO_NOTE["ru"])


class DemoProvider:
    name = "demo"
    demo_mode = True

    def recognize(
        self,
        images: list[ImageInput],
        typed_text: str,
        language: str,
        grade_number: int,
        subjects: list[SubjectOption],
    ) -> tuple[RecognitionResult, Usage]:
        if typed_text.strip():
            parts = _split_tasks(typed_text)
            math_slug = next((s.slug for s in subjects if s.slug in ("math", "algebra")), None)
            tasks = [
                RecognizedTask(
                    index=i,
                    label=f"№ {i + 1}" if len(parts) > 1 else "",
                    text=chunk,
                    language=language,
                    subject_slug=math_slug if _looks_like_math(chunk) else None,
                    task_type="calculation" if _looks_like_math(chunk) else "exercise",
                    confidence=0.4,
                )
                for i, chunk in enumerate(parts)
            ]
            return RecognitionResult(readable=True, tasks=tasks, notes=_note(language)), Usage(model="demo")
        if images:
            return (
                RecognitionResult(
                    readable=False,
                    unreadable_reason="В демо-режиме фотографии не распознаются. Введи текст задания вручную.",
                    notes=_note(language),
                ),
                Usage(model="demo"),
            )
        raise AIProviderError("Nothing to recognize", code="empty_input")

    def respond(self, context: TutorContext, command: str, user_message: str) -> Iterator[StreamChunk]:
        turn = _demo_turn(context, command, user_message)
        for piece in _chunks(turn.message):
            yield StreamChunk(text=piece)
        yield StreamChunk(final=turn, usage=Usage(model="demo"))

    def generate_quiz(self, request: QuizRequest) -> tuple[QuizSpec, Usage]:
        """Maths: real arithmetic questions built by rules. Anything else needs the AI provider."""
        if request.subject_strategy == "math":
            return build_math_quiz(request), Usage(model="rules")
        raise AIProviderError(
            "Проверка по этой теме появится после подключения AI-провайдера.",
            code="demo_mode",
            retryable=False,
        )

    def assess(
        self, context: TutorContext, answer: str, rubric: list[str], expected_answer: str | None
    ) -> tuple[AssessmentResult, Usage]:
        return (
            AssessmentResult(
                verdict="uncertain",
                confidence=0.0,
                feedback=(
                    "Демо-режим не умеет проверять развёрнутые ответы. "
                    "Когда подключат AI-провайдер, здесь будет настоящая проверка."
                ),
            ),
            Usage(model="demo"),
        )


def _split_tasks(text: str) -> list[str]:
    parts = re.split(r"(?:^|\n)\s*(?:№\s*\d+|\d+[).])\s*", text.strip())
    parts = [p.strip() for p in parts if p and p.strip()]
    return parts or [text.strip()]


def _looks_like_math(text: str) -> bool:
    return bool(re.search(r"\d\s*[+\-*/×:=]\s*\d|\bx\b|дроб|уравнен|вычисл|реши", text.lower()))


def _chunks(text: str, size: int = 24) -> Iterator[str]:
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _expected_for(task: str) -> tuple[str | None, str]:
    """A tiny bit of real arithmetic so question → check can be exercised without a key."""
    match = _SIMPLE_EQUATION.match(task.replace("×", "*").replace(":", "/"))
    if not match:
        return None, "text"
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    if op == "/" and b == 0:
        return None, "text"
    value = {"+": a + b, "-": a - b, "*": a * b, "/": a / b}[op]
    return (str(int(value)) if float(value).is_integer() else str(value)), "number"


def _demo_turn(context: TutorContext, command: str, user_message: str) -> TutorTurn:
    lang = context.language
    note = _note(lang)
    task = (context.assignment_text or user_message or "").strip()
    short_task = task[:300] + ("…" if len(task) > 300 else "")
    subject = context.subject_name or ("Сабак" if lang == "ky" else "Предмет")
    expected, kind = _expected_for(task)

    if command in ("start", "repeat", ""):
        message = (
            f"Давай разберёмся, что здесь нужно сделать.\n\n"
            f"**Задание:** {short_task or '—'}\n\n"
            f"1. Прочитай условие ещё раз и найди, что дано и что нужно найти.\n"
            f"2. Вспомни правило или формулу по теме «{context.topic_name or subject}».\n"
            f"3. Сделай первый шаг сам и напиши мне, что получилось.\n\n_{note}_"
        )
        return TutorTurn(
            message=message,
            steps=[
                TutorStep(title="Что дано", content="Выпиши известные данные из условия."),
                TutorStep(title="Что найти", content="Сформулируй вопрос задачи своими словами."),
                TutorStep(title="Первый шаг", content="Выбери правило или действие, с которого начнёшь."),
            ],
            check_question="Какой ответ у тебя получился?" if expected else "С чего начнёшь решение?",
            expected_answer=expected,
            answer_kind=kind,
            suggested_commands=["hint", "example", "simpler"],
            uncertainty_note=note,
        )
    texts = {
        "hint": "Подсказка: обрати внимание на ключевые слова в условии и на то, какое действие они подсказывают.",
        "example": "Похожий пример: возьми задачу попроще с теми же шагами и реши её сначала.",
        "simpler": "Объясняю проще: разбей задание на маленькие шаги и делай по одному.",
        "why": "Почему так: каждое действие следует из правила темы. Назови правило, которое применяешь.",
        "dont_understand": "Ничего страшного. Скажи, какой именно шаг непонятен, и начнём с него.",
        "similar": "Похожая задача появится, когда будет подключён AI-провайдер.",
        "next_step": "Хорошо. Переходи к следующему шагу и напиши, что получилось.",
    }
    message = texts.get(command) or (
        f"Ты написал: «{user_message[:200]}». В демо-режиме я могу только подсказать направление."
    )
    return TutorTurn(
        message=f"{message}\n\n_{note}_",
        check_question="Какой ответ у тебя получился?" if expected else "",
        expected_answer=expected,
        answer_kind=kind if expected else "none",
        suggested_commands=["hint", "example", "check"],
        uncertainty_note=note,
    )
