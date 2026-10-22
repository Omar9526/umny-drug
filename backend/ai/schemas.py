"""Strict schemas for everything a model returns. Invalid output is rejected, never shown to a child."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Language = Literal["ru", "ky"]

TASK_TYPES = (
    "calculation",
    "equation",
    "word_problem",
    "exercise",
    "essay",
    "reading",
    "translation",
    "test",
    "other",
)


class RecognizedTask(BaseModel):
    index: int = Field(ge=0, le=20, description="Порядковый номер задания на фото, начиная с 0")
    label: str = Field(default="", max_length=40, description="Подпись как в учебнике: «№ 3», «Упр. 12»")
    text: str = Field(min_length=1, max_length=6000, description="Полный текст условия, формулы в $...$")
    subject_slug: str | None = Field(default=None, max_length=48, description="Slug предмета из списка")
    topic_hint: str | None = Field(default=None, max_length=160, description="Тема своими словами")
    task_type: str = Field(default="other", max_length=32)
    language: Language = "ru"
    confidence: float = Field(default=0.5, ge=0, le=1)
    has_formula: bool = False
    has_figure: bool = False

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("task_type")
    @classmethod
    def known_task_type(cls, value: str) -> str:
        return value if value in TASK_TYPES else "other"


class RecognitionResult(BaseModel):
    readable: bool = Field(description="False, если текст заданий прочитать нельзя")
    tasks: list[RecognizedTask] = Field(default_factory=list, max_length=20)
    unreadable_reason: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=500)

    @field_validator("tasks")
    @classmethod
    def unique_indexes(cls, tasks: list[RecognizedTask]) -> list[RecognizedTask]:
        seen: set[int] = set()
        for task in tasks:
            if task.index in seen:
                raise ValueError("duplicate task index")
            seen.add(task.index)
        return tasks


class TutorStep(BaseModel):
    title: str = Field(max_length=160)
    content: str = Field(max_length=4000)


AnswerKind = Literal["number", "expression", "text", "choice", "none"]

MAX_TURN_MESSAGE = 8000


class TutorMeta(BaseModel):
    """Structured tail of a tutor turn (everything except the visible message)."""

    steps: list[TutorStep] = Field(default_factory=list, max_length=12)
    check_question: str = Field(default="", max_length=600)
    expected_answer: str | None = Field(default=None, max_length=400)
    answer_kind: AnswerKind = "none"
    # True when check_question asks for the task's final answer; False for an intermediate step.
    is_final_answer: bool = True
    rubric: list[str] = Field(default_factory=list, max_length=8)
    reveals_solution: bool = False
    uncertainty_note: str = Field(default="", max_length=400)
    suggested_commands: list[str] = Field(default_factory=list, max_length=6)
    off_topic: bool = False


class TutorTurn(TutorMeta):
    """One assistant turn. ``message`` is markdown with KaTeX-style $...$ formulas."""

    message: str = Field(min_length=1, max_length=MAX_TURN_MESSAGE)


class AssessmentResult(BaseModel):
    verdict: Literal["correct", "partial", "incorrect", "uncertain"]
    confidence: float = Field(ge=0, le=1)
    feedback: str = Field(min_length=1, max_length=3000, description="Отзыв для ребёнка на его языке")
    criteria: list[dict] = Field(default_factory=list, max_length=12)
    next_hint: str = Field(default="", max_length=800)


class QuizQuestion(BaseModel):
    """One self-check question. Correct answers live only on the server; the client gets a stripped copy."""

    kind: Literal["choice", "number", "short"]
    prompt: str = Field(min_length=3, max_length=600)
    options: list[str] = Field(
        default_factory=list, max_length=4, description="Только для kind=choice, 2–4 варианта"
    )
    correct_option: int | None = Field(
        default=None, ge=0, le=3, description="Индекс верного варианта для choice"
    )
    answer: str = Field(default="", max_length=200, description="Ожидаемый ответ для number/short")
    accepted: list[str] = Field(
        default_factory=list, max_length=6, description="Допустимые варианты для short"
    )
    explanation: str = Field(min_length=1, max_length=600)
    hint: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _consistent(self):
        if self.kind == "choice":
            if not 2 <= len(self.options) <= 4:
                raise ValueError("choice question needs 2–4 options")
            if self.correct_option is None or self.correct_option >= len(self.options):
                raise ValueError("correct_option must point at an option")
        elif not self.answer.strip():
            raise ValueError("number/short question needs an answer")
        return self


class QuizSpec(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    questions: list[QuizQuestion] = Field(min_length=3, max_length=5)
