"""Provider-agnostic contract for the tutor engine.

A provider must implement three operations:

* ``recognize``   — photos / typed text → structured list of tasks (OCR + segmentation + subject hints);
* ``respond``     — a tutoring turn (streamed) given the session context and a quick command;
* ``assess``      — rubric-based assessment of an open answer when no formal verifier applies.

Everything that leaves a provider is validated against the pydantic schemas in ``ai.schemas``
before it is stored or shown to a child.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from .schemas import AssessmentResult, RecognitionResult, TutorTurn


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    latency_ms: int = 0


class AIProviderError(Exception):
    """Raised for provider failures the caller should handle gracefully (timeouts, quota, bad output).

    ``usage`` carries tokens that were already billed before the failure (refusal, truncation), so
    the caller can still record them for cost monitoring.
    """

    def __init__(
        self, message: str, *, code: str = "ai_error", retryable: bool = False, usage: Usage | None = None
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.usage = usage


@dataclass
class ImageInput:
    data: bytes
    mime_type: str


@dataclass
class SubjectOption:
    slug: str
    name: str


@dataclass
class TutorContext:
    """Everything the tutor needs to answer one turn. Built server-side; never trusts client input."""

    grade_number: int
    stage: str  # primary | middle | senior
    language: str  # ru | ky
    mode: str  # homework | question | explain_topic | check_answer | exam_prep | practice
    student_nickname: str = ""
    subject_slug: str | None = None
    subject_name: str | None = None
    subject_strategy: str | None = None
    subject_notes: str = ""
    topic_name: str | None = None
    assignment_text: str | None = None
    history: list[dict] = field(default_factory=list)  # [{"role": "user"|"assistant", "content": str}]
    hints_used: int = 0
    attempts: list[dict] = field(default_factory=list)  # [{"answer": str, "verdict": str}]
    solution_revealed: bool = False


@dataclass
class QuizRequest:
    """What the provider needs to write a short self-check on one curriculum topic."""

    topic_name: str
    topic_description: str
    keywords: list[str]
    subject_name: str
    subject_strategy: str
    subject_notes: str
    grade_number: int
    language: str
    count: int = 4


@dataclass
class StreamChunk:
    """A piece of a streamed tutor turn.

    ``text`` chunks arrive first; ``reset`` tells the client to discard text shown so far (a safety
    fallback replaced the declined draft); ``final`` carries the parsed turn.
    """

    text: str = ""
    reset: bool = False
    final: TutorTurn | None = None
    usage: Usage | None = None


if TYPE_CHECKING:
    from .schemas import QuizSpec


class AIProvider(Protocol):
    name: str
    demo_mode: bool

    def recognize(
        self,
        images: list[ImageInput],
        typed_text: str,
        language: str,
        grade_number: int,
        subjects: list[SubjectOption],
    ) -> tuple[RecognitionResult, Usage]: ...

    def respond(self, context: TutorContext, command: str, user_message: str) -> Iterator[StreamChunk]: ...

    def generate_quiz(self, request: QuizRequest) -> tuple[QuizSpec, Usage]: ...

    def assess(
        self, context: TutorContext, answer: str, rubric: list[str], expected_answer: str | None
    ) -> tuple[AssessmentResult, Usage]: ...
