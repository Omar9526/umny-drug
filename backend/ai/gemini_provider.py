"""Google Gemini provider (Gemini Developer API through the ``google-genai`` SDK).

Same contract as the Anthropic provider:

* ``recognize``, ``assess`` and ``generate_quiz`` ask for JSON constrained by our pydantic schemas
  (``response_schema``) and validate the result again on our side;
* ``respond`` streams the visible explanation and parses the ``<meta>…</meta>`` tail at the end.

The Developer API rejects free-form objects in schemas, so the assessment uses a typed criteria
model and converts it back to ``AssessmentResult``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Literal

import httpx
from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from .base import AIProviderError, ImageInput, QuizRequest, StreamChunk, SubjectOption, TutorContext, Usage
from .costs import estimate_cost
from .prompts import (
    ASSESSMENT_SYSTEM,
    RECOGNITION_SYSTEM,
    build_assessment_prompt,
    build_recognition_prompt,
    build_session_block,
    build_system_prompt,
    user_turn_text,
)
from .prompts.quiz import QUIZ_SYSTEM, build_quiz_prompt
from .schemas import AssessmentResult, QuizSpec, RecognitionResult
from .turns import parse_turn, split_visible

logger = logging.getLogger("umnydrug.ai")

REFUSAL_FINISH_REASONS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"}
SESSION_OPENER = "Начинаем занятие."
# Recognition usually takes 2–5 s; the lite model occasionally stalls for 30 s+, so cap one attempt
# and let the SDK retry twice (measured: a retry after a stall answers in ~3 s).
RECOGNITION_TIMEOUT_S = 12
RECOGNITION_ATTEMPTS = 3
# Assessment and quiz generation: a stalled attempt must not hold a worker for the full 90 s.
STRUCTURED_TIMEOUT_S = 30


class Criterion(BaseModel):
    name: str = Field(max_length=200)
    met: bool = False
    comment: str = Field(default="", max_length=500)


class GeminiAssessment(BaseModel):
    """``AssessmentResult`` with typed criteria (the API schema cannot express ``list[dict]``)."""

    verdict: Literal["correct", "partial", "incorrect", "uncertain"]
    confidence: float = Field(ge=0, le=1)
    feedback: str = Field(min_length=1, max_length=3000)
    criteria: list[Criterion] = Field(default_factory=list, max_length=12)
    next_hint: str = Field(default="", max_length=800)

    def to_result(self) -> AssessmentResult:
        return AssessmentResult(
            verdict=self.verdict,
            confidence=self.confidence,
            feedback=self.feedback,
            criteria=[c.model_dump() for c in self.criteria],
            next_hint=self.next_hint,
        )


def _finish_reason(response) -> str:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""
    reason = getattr(candidates[0], "finish_reason", None)
    if reason is None:
        return ""
    return getattr(reason, "name", None) or str(reason).split(".")[-1]


def _blocked(response) -> bool:
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        return True
    return _finish_reason(response) in REFUSAL_FINISH_REASONS


def _text_parts(chunk) -> str:
    """Concatenate visible text parts of a chunk; thought parts never reach the child."""
    out = []
    for candidate in getattr(chunk, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in (getattr(content, "parts", None) or []) if content else []:
            text = getattr(part, "text", None)
            if text and not getattr(part, "thought", False):
                out.append(text)
    return "".join(out)


def _usage_from(response, model: str, started: float) -> Usage:
    raw = getattr(response, "usage_metadata", None)
    get = lambda name: getattr(raw, name, 0) or 0  # noqa: E731
    cached = get("cached_content_token_count")
    usage = Usage(
        # prompt_token_count already includes the cached part; keep input = uncached, like Anthropic
        input_tokens=max(get("prompt_token_count") - cached, 0),
        # Thinking tokens are billed as output.
        output_tokens=get("candidates_token_count") + get("thoughts_token_count"),
        cache_read_tokens=cached,
        model=getattr(response, "model_version", None) or model,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    usage.cost_usd = estimate_cost(usage.model, usage) or estimate_cost(model, usage)
    return usage


def _map_error(exc: Exception) -> AIProviderError:
    if isinstance(exc, AIProviderError):
        return exc
    if isinstance(exc, genai_errors.APIError):
        status = int(getattr(exc, "code", 0) or 0)
        if status in (401, 403):
            return AIProviderError("AI-провайдер отклонил ключ доступа.", code="auth")
        if status == 429:
            return AIProviderError(
                "Помощник сейчас перегружен. Попробуй через минуту.", code="rate_limited", retryable=True
            )
        if status == 404:
            return AIProviderError("Модель AI-провайдера недоступна.", code="bad_request")
        if status == 400 and "api key" in str(exc).lower():  # the Developer API answers 400 to a bad key
            return AIProviderError("AI-провайдер отклонил ключ доступа.", code="auth")
        if 400 <= status < 500:
            return AIProviderError("Запрос к AI не принят. Мы уже разбираемся.", code="bad_request")
        return AIProviderError("AI-провайдер временно недоступен.", code=f"http_{status}", retryable=True)
    if isinstance(exc, httpx.TimeoutException):
        return AIProviderError(
            "Помощник отвечал слишком долго. Попробуй ещё раз.", code="timeout", retryable=True
        )
    if isinstance(exc, httpx.HTTPError | ConnectionError):
        return AIProviderError("Нет связи с AI-провайдером.", code="connection", retryable=True)
    if isinstance(exc, ValidationError):
        return AIProviderError("Ответ AI не прошёл проверку.", code="invalid_output", retryable=True)
    return AIProviderError("Непредвиденная ошибка AI-провайдера.", code="unknown")


def _thinking(model: str, level: str | None = None) -> types.ThinkingConfig:
    """Gemini 2.x takes a token budget, newer generations a level."""
    if model.startswith("gemini-2"):
        return types.ThinkingConfig(thinking_budget=512, include_thoughts=False)
    return types.ThinkingConfig(
        thinking_level=level or settings.GEMINI_THINKING_LEVEL, include_thoughts=False
    )


def history_to_contents(history: list[dict], user_text: str) -> list[types.Content]:
    """Map our ``user``/``assistant`` history to Gemini contents (first content must be the user's)."""
    contents: list[types.Content] = []
    for item in history:
        text = (item.get("content") or "").strip()
        if not text:
            continue
        role = "model" if item.get("role") == "assistant" else "user"
        if contents and contents[-1].role == role:
            contents[-1].parts.append(types.Part.from_text(text=text))
        else:
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
    if contents and contents[0].role == "model":
        contents.insert(0, types.Content(role="user", parts=[types.Part.from_text(text=SESSION_OPENER)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))
    return contents


class GeminiProvider:
    name = "gemini"
    demo_mode = False

    def __init__(self, client: genai.Client | None = None) -> None:
        self._client = client or genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.AI_REQUEST_TIMEOUT_SECONDS * 1000,
                retry_options=types.HttpRetryOptions(attempts=2),
            ),
        )

    def _structured(
        self,
        *,
        model: str,
        system: str,
        contents,
        schema,
        max_tokens: int,
        level: str,
        timeout_s: float | None = None,
        attempts: int = 2,
    ):
        """One JSON-constrained call; returns (parsed instance, usage) or raises a domain error.

        ``timeout_s`` bounds a single attempt: the SDK retries transient failures (timeouts included),
        so an occasional 30-second stall on the provider side turns into timeout + one quick retry.
        """
        started = time.monotonic()
        http_options = (
            types.HttpOptions(
                timeout=int(timeout_s * 1000),
                retry_options=types.HttpRetryOptions(attempts=attempts),
            )
            if timeout_s
            else None
        )
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=max_tokens,
                    temperature=0.3,
                    thinking_config=_thinking(model, level),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    http_options=http_options,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a domain error
            raise _map_error(exc) from exc
        usage = _usage_from(response, model, started)
        if _blocked(response):
            raise AIProviderError("Это нельзя обработать.", code="refused", usage=usage)
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            try:
                parsed = schema.model_validate_json(response.text or "")
            except (ValidationError, ValueError):
                parsed = None
        if parsed is None:
            raise AIProviderError(
                "Не удалось разобрать ответ AI.", code="invalid_output", retryable=True, usage=usage
            )
        return parsed, usage

    # ------------------------------------------------------------------ recognize
    def recognize(
        self,
        images: list[ImageInput],
        typed_text: str,
        language: str,
        grade_number: int,
        subjects: list[SubjectOption],
    ) -> tuple[RecognitionResult, Usage]:
        if not images and not typed_text.strip():
            raise AIProviderError("Nothing to recognize", code="empty_input")
        parts = [types.Part.from_bytes(data=image.data, mime_type=image.mime_type) for image in images]
        parts.append(
            types.Part.from_text(
                text=build_recognition_prompt(
                    typed_text=typed_text,
                    language=language,
                    grade_number=grade_number,
                    subjects=subjects,
                    image_count=len(images),
                )
            )
        )
        parsed, usage = self._structured(
            model=settings.GEMINI_MODEL_VISION,
            system=RECOGNITION_SYSTEM,
            contents=[types.Content(role="user", parts=parts)],
            schema=RecognitionResult,
            max_tokens=8000,
            level="low",
            timeout_s=RECOGNITION_TIMEOUT_S,
            attempts=RECOGNITION_ATTEMPTS,
        )
        return parsed, usage

    # ------------------------------------------------------------------ respond
    def respond(self, context: TutorContext, command: str, user_message: str) -> Iterator[StreamChunk]:
        model = settings.GEMINI_MODEL
        contents = history_to_contents(
            context.history, user_turn_text(command, user_message, context.language)
        )
        config = types.GenerateContentConfig(
            system_instruction=[build_system_prompt(context), build_session_block(context)],
            max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            temperature=0.7,
            thinking_config=_thinking(model, "low" if context.stage == "primary" else None),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        started = time.monotonic()
        buffer = ""
        emitted = 0
        meta_seen = False
        last = None
        try:
            for chunk in self._client.models.generate_content_stream(
                model=model, contents=contents, config=config
            ):
                last = chunk
                feedback = getattr(chunk, "prompt_feedback", None)
                if feedback is not None and getattr(feedback, "block_reason", None):
                    raise AIProviderError(
                        "Помощник не может ответить на это. Давай вернёмся к заданию.",
                        code="refused",
                        usage=_usage_from(chunk, model, started),
                    )
                buffer += _text_parts(chunk)
                visible, meta_seen = split_visible(buffer, meta_seen)
                if len(visible) > emitted:
                    yield StreamChunk(text=visible[emitted:])
                    emitted = len(visible)
        except AIProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc

        usage = _usage_from(last, model, started) if last is not None else Usage(model=model)
        reason = _finish_reason(last) if last is not None else ""
        if reason in REFUSAL_FINISH_REASONS:
            raise AIProviderError(
                "Помощник не может ответить на это. Давай вернёмся к заданию.", code="refused", usage=usage
            )
        turn = parse_turn(buffer)
        if reason == "MAX_TOKENS":
            turn.uncertainty_note = (turn.uncertainty_note + " Ответ был обрезан по длине.").strip()
        remaining = turn.message[emitted:] if len(turn.message) > emitted else ""
        if remaining:
            yield StreamChunk(text=remaining)
        yield StreamChunk(final=turn, usage=usage)

    # ------------------------------------------------------------------ assess
    def assess(
        self, context: TutorContext, answer: str, rubric: list[str], expected_answer: str | None
    ) -> tuple[AssessmentResult, Usage]:
        check_question = ""
        for item in reversed(context.history):
            if item.get("role") == "assistant" and item.get("check_question"):
                check_question = item["check_question"]
                break
        prompt = build_assessment_prompt(
            context=context,
            answer=answer,
            rubric=rubric,
            expected_answer=expected_answer,
            check_question=check_question,
        )
        parsed, usage = self._structured(
            model=settings.GEMINI_MODEL,
            system=ASSESSMENT_SYSTEM,
            contents=prompt,
            schema=GeminiAssessment,
            max_tokens=4000,
            level="low",
            timeout_s=STRUCTURED_TIMEOUT_S,
        )
        return parsed.to_result(), usage

    # ------------------------------------------------------------------ quiz
    def generate_quiz(self, request: QuizRequest) -> tuple[QuizSpec, Usage]:
        spec, usage = self._structured(
            model=settings.GEMINI_MODEL,
            system=QUIZ_SYSTEM,
            contents=build_quiz_prompt(request),
            schema=QuizSpec,
            max_tokens=4000,
            level=settings.GEMINI_THINKING_LEVEL,
            timeout_s=STRUCTURED_TIMEOUT_S,
        )
        if len(spec.questions) != request.count:
            spec = QuizSpec(title=spec.title, questions=spec.questions[: max(3, request.count)])
        return spec, usage
