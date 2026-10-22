"""Anthropic (Claude) provider.

* ``recognize`` and ``assess`` use structured outputs (``messages.parse`` + pydantic) so the
  response is schema-valid by construction.
* ``respond`` streams the visible explanation token by token and parses the structured
  ``<meta>…</meta>`` tail at the end. Streaming goes through ``beta.messages.stream`` with
  server-side refusal fallbacks enabled; if the beta is rejected the turn is retried as a plain
  stream. A mid-stream fallback (a ``fallback`` content block) resets what the client has shown.
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Iterator

import anthropic
from django.conf import settings

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
from .turns import META_CLOSE, META_INVALID_NOTE, META_OPEN, parse_turn, split_visible  # noqa: F401 - re-exported

logger = logging.getLogger("umnydrug.ai")

FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _usage_from(message, model: str, started: float) -> Usage:
    raw = getattr(message, "usage", None)
    usage = Usage(
        input_tokens=getattr(raw, "input_tokens", 0) or 0,
        output_tokens=getattr(raw, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(raw, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(raw, "cache_creation_input_tokens", 0) or 0,
        model=getattr(message, "model", None) or model,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    usage.cost_usd = estimate_cost(usage.model, usage)
    return usage


def _map_error(exc: Exception) -> AIProviderError:
    if isinstance(exc, anthropic.AuthenticationError):
        return AIProviderError("AI-провайдер отклонил ключ доступа.", code="auth")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return AIProviderError("У ключа AI-провайдера нет нужных прав.", code="auth")
    if isinstance(exc, anthropic.RateLimitError):
        return AIProviderError(
            "Помощник сейчас перегружен. Попробуй через минуту.", code="rate_limited", retryable=True
        )
    if isinstance(exc, anthropic.APITimeoutError):
        return AIProviderError(
            "Помощник отвечал слишком долго. Попробуй ещё раз.", code="timeout", retryable=True
        )
    if isinstance(exc, anthropic.BadRequestError):
        return AIProviderError("Запрос к AI не принят. Мы уже разбираемся.", code="bad_request")
    if isinstance(exc, anthropic.APIStatusError):
        retryable = exc.status_code >= 500
        return AIProviderError(
            "AI-провайдер временно недоступен.", code=f"http_{exc.status_code}", retryable=retryable
        )
    if isinstance(exc, anthropic.APIConnectionError):
        return AIProviderError("Нет связи с AI-провайдером.", code="connection", retryable=True)
    return AIProviderError("Непредвиденная ошибка AI-провайдера.", code="unknown")


class AnthropicProvider:
    name = "anthropic"
    demo_mode = False

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=2,
        )

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
        content: list[dict] = []
        for image in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.mime_type,
                        "data": base64.standard_b64encode(image.data).decode("ascii"),
                    },
                }
            )
        content.append(
            {
                "type": "text",
                "text": build_recognition_prompt(
                    typed_text=typed_text,
                    language=language,
                    grade_number=grade_number,
                    subjects=subjects,
                    image_count=len(images),
                ),
            }
        )
        model = settings.AI_MODEL_VISION
        started = time.monotonic()
        try:
            response = self._client.messages.parse(
                model=model,
                max_tokens=8000,
                system=RECOGNITION_SYSTEM,
                messages=[{"role": "user", "content": content}],
                output_format=RecognitionResult,
                output_config={"effort": "medium"},
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a domain error below
            raise _map_error(exc) from exc
        usage = _usage_from(response, model, started)
        if response.stop_reason == "refusal":
            raise AIProviderError("Это изображение нельзя обработать.", code="refused", usage=usage)
        parsed = response.parsed_output
        if parsed is None:
            raise AIProviderError(
                "Не удалось разобрать ответ распознавания.",
                code="invalid_output",
                retryable=True,
                usage=usage,
            )
        return parsed, usage

    # ------------------------------------------------------------------ respond
    def respond(self, context: TutorContext, command: str, user_message: str) -> Iterator[StreamChunk]:
        system = [
            {"type": "text", "text": build_system_prompt(context), "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": build_session_block(context)},
        ]
        messages = [{"role": m["role"], "content": m["content"]} for m in context.history if m.get("content")]
        messages.append({"role": "user", "content": user_turn_text(command, user_message, context.language)})
        kwargs = dict(
            model=settings.AI_MODEL_TUTOR,
            max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            system=system,
            messages=messages,
            output_config={"effort": "low" if context.stage == "primary" else "medium"},
        )
        try:
            yield from self._stream_turn(kwargs, use_fallbacks=True)
        except _FallbackRejected:
            logger.warning(
                "fallbacks beta rejected, streaming without it", extra={"event": "ai.fallbacks_off"}
            )
            yield from self._stream_turn(kwargs, use_fallbacks=False)

    def _open(self, kwargs: dict, use_fallbacks: bool):
        if use_fallbacks:
            return self._client.beta.messages.stream(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
        return self._client.messages.stream(**kwargs)

    def _stream_turn(self, kwargs: dict, *, use_fallbacks: bool) -> Iterator[StreamChunk]:
        model = kwargs["model"]
        started = time.monotonic()
        buffer = ""
        emitted = 0
        meta_seen = False
        yielded_anything = False
        manager = self._open(kwargs, use_fallbacks)
        try:
            stream = manager.__enter__()  # the HTTP request is sent here, not in .stream()
        except anthropic.BadRequestError as exc:
            if use_fallbacks and "fallback" in str(exc).lower():
                raise _FallbackRejected() from exc
            raise _map_error(exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc
        try:
            for event in stream:
                if event.type == "content_block_start":
                    if getattr(event.content_block, "type", "") == "fallback":
                        # The first model declined mid-answer; another model continues from scratch.
                        buffer, emitted, meta_seen = "", 0, False
                        yield StreamChunk(reset=True)
                elif event.type == "content_block_delta" and getattr(event.delta, "type", "") == "text_delta":
                    buffer += event.delta.text
                    visible, meta_seen = split_visible(buffer, meta_seen)
                    if len(visible) > emitted:
                        yield StreamChunk(text=visible[emitted:])
                        emitted = len(visible)
                        yielded_anything = True
            final = stream.get_final_message()
        except AIProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            if (
                not yielded_anything
                and use_fallbacks
                and isinstance(exc, anthropic.BadRequestError)
                and "fallback" in str(exc).lower()
            ):
                raise _FallbackRejected() from exc
            raise _map_error(exc) from exc
        finally:
            manager.__exit__(None, None, None)

        usage = _usage_from(final, model, started)
        if final.stop_reason == "refusal":
            raise AIProviderError(
                "Помощник не может ответить на это. Давай вернёмся к заданию.", code="refused", usage=usage
            )
        turn = parse_turn(buffer)
        if final.stop_reason == "max_tokens":
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
        model = settings.AI_MODEL_VERIFY
        started = time.monotonic()
        try:
            response = self._client.messages.parse(
                model=model,
                max_tokens=4000,
                system=ASSESSMENT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=AssessmentResult,
                output_config={"effort": "medium"},
            )
        except Exception as exc:  # noqa: BLE001
            raise _map_error(exc) from exc
        usage = _usage_from(response, model, started)
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise AIProviderError(
                "Не удалось проверить ответ.", code="invalid_output", retryable=True, usage=usage
            )
        return response.parsed_output, usage


def _generate_quiz(self: AnthropicProvider, request: QuizRequest) -> tuple[QuizSpec, Usage]:
    model = settings.AI_MODEL_TUTOR
    started = time.monotonic()
    try:
        response = self._client.messages.parse(
            model=model,
            max_tokens=4000,
            system=QUIZ_SYSTEM,
            messages=[{"role": "user", "content": build_quiz_prompt(request)}],
            output_format=QuizSpec,
            output_config={"effort": "medium"},
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc
    usage = _usage_from(response, model, started)
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise AIProviderError(
            "Не удалось составить проверку.", code="invalid_output", retryable=True, usage=usage
        )
    spec = response.parsed_output
    if len(spec.questions) != request.count:
        spec = QuizSpec(title=spec.title, questions=spec.questions[: max(3, request.count)])
    return spec, usage


AnthropicProvider.generate_quiz = _generate_quiz


class _FallbackRejected(Exception):
    """Internal: the server-side fallback beta was refused by the API; retry without it."""
