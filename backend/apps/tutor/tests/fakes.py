"""Scripted AI provider for end-to-end tests of the tutoring flow (no network, deterministic)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ai.base import AIProviderError, ImageInput, QuizRequest, StreamChunk, SubjectOption, TutorContext, Usage
from ai.registry import set_provider_override
from ai.schemas import (
    AssessmentResult,
    QuizQuestion,
    QuizSpec,
    RecognitionResult,
    RecognizedTask,
    TutorStep,
    TutorTurn,
)


class ScriptedProvider:
    name = "fake"
    demo_mode = False

    def __init__(self):
        self.recognize_calls = 0
        self.respond_calls: list[tuple[str, str]] = []
        self.assess_calls = 0
        self.final_answer = True  # is_final_answer on every turn
        self.fail_next = False  # raise a retryable error on the next respond()
        self.respond_usage = Usage(input_tokens=800, output_tokens=120, model="fake-tutor", latency_ms=30)

    def recognize(
        self,
        images: list[ImageInput],
        typed_text: str,
        language: str,
        grade_number: int,
        subjects: list[SubjectOption],
    ) -> tuple[RecognitionResult, Usage]:
        self.recognize_calls += 1
        math = next((s.slug for s in subjects if s.slug == "math"), None)
        tasks = [
            RecognizedTask(
                index=0,
                label="№ 1",
                text="Реши уравнение $2x + 3 = 11$.",
                subject_slug=math,
                topic_hint="уравнения",
                task_type="equation",
                has_formula=True,
                confidence=0.9,
            ),
            RecognizedTask(
                index=1,
                label="№ 2",
                text="Найди значение выражения $3 \\cdot 4 + 2$.",
                subject_slug=math,
                topic_hint="порядок действий",
                task_type="calculation",
                confidence=0.85,
            ),
        ]
        return RecognitionResult(readable=True, tasks=tasks), Usage(
            input_tokens=1200, output_tokens=200, model="fake-vision", latency_ms=50
        )

    def respond(self, context: TutorContext, command: str, user_message: str) -> Iterator[StreamChunk]:
        self.respond_calls.append((command, user_message))
        if self.fail_next:
            self.fail_next = False
            raise AIProviderError("Помощник перегружен.", code="rate_limited", retryable=True)
        if command == "hint":
            turn = TutorTurn(
                message="Подсказка: перенеси 3 в правую часть. Что останется слева?",
                check_question="Чему равен x?",
                expected_answer="4",
                answer_kind="number",
                is_final_answer=self.final_answer,
                suggested_commands=["example"],
            )
        else:
            turn = TutorTurn(
                message="Давай разберёмся. У нас уравнение $2x + 3 = 11$. Сначала уберём 3.",
                steps=[TutorStep(title="Что дано", content="2x + 3 = 11")],
                check_question="Чему равен x?",
                expected_answer="4",
                answer_kind="number",
                is_final_answer=self.final_answer,
                suggested_commands=["hint", "example"],
            )
        for piece in (turn.message[:20], turn.message[20:]):
            yield StreamChunk(text=piece)
        yield StreamChunk(final=turn, usage=self.respond_usage)

    def generate_quiz(self, request: QuizRequest) -> tuple[QuizSpec, Usage]:
        self.quiz_calls = getattr(self, "quiz_calls", 0) + 1
        if getattr(self, "quiz_fail", None):
            raise AIProviderError("quiz failed", code=self.quiz_fail)
        questions = [
            QuizQuestion(
                kind="choice",
                prompt=f"Вопрос 1 по теме «{request.topic_name}»",
                options=["верный", "неверный", "тоже неверный"],
                correct_option=0,
                explanation="Потому что так.",
                hint="Подумай.",
            ),
            QuizQuestion(
                kind="number", prompt="Сколько будет 6 × 7?", answer="42", explanation="6 × 7 = 42."
            ),
            QuizQuestion(
                kind="short",
                prompt="Как называется результат сложения?",
                answer="сумма",
                accepted=["сумма", "Сумма"],
                explanation="Результат сложения — сумма.",
            ),
        ]
        return QuizSpec(
            title=f"Проверка: {request.topic_name}", questions=questions[: max(3, request.count)]
        ), Usage(input_tokens=500, output_tokens=200, model="fake-quiz")

    def assess(self, context: TutorContext, answer: str, rubric: list[str], expected_answer: str | None):
        self.assess_calls += 1
        return (
            AssessmentResult(
                verdict="partial",
                confidence=0.6,
                feedback="Почти, уточни вторую часть.",
                next_hint="Вспомни правило.",
            ),
            Usage(input_tokens=300, output_tokens=60, model="fake-judge"),
        )


@pytest.fixture
def fake_provider():
    provider = ScriptedProvider()
    set_provider_override(provider)
    yield provider
    set_provider_override(None)
