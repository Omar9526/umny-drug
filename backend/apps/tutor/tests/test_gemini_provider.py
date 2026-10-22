"""Gemini provider: pure logic around the SDK (history mapping, streaming, schema conversion, errors).

No network: the client is replaced by small fakes shaped like ``google.genai`` responses.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors

from ai.base import AIProviderError, TutorContext
from ai.gemini_provider import (
    GeminiAssessment,
    GeminiProvider,
    _map_error,
    _usage_from,
    history_to_contents,
)


def _chunk(text: str, *, finish: str | None = None, usage=None):
    part = SimpleNamespace(text=text, thought=False)
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[part]),
        finish_reason=SimpleNamespace(name=finish) if finish else None,
    )
    return SimpleNamespace(
        candidates=[candidate], prompt_feedback=None, usage_metadata=usage, model_version=None
    )


def _usage(prompt=10, out=20, thoughts=5, cached=0):
    return SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=out,
        thoughts_token_count=thoughts,
        cached_content_token_count=cached,
    )


class FakeModels:
    def __init__(self, *, chunks=None, response=None):
        self.chunks = chunks or []
        self.response = response
        self.calls: list[dict] = []

    def generate_content_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield from self.chunks

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _provider(models: FakeModels) -> GeminiProvider:
    return GeminiProvider(client=SimpleNamespace(models=models))


def _context(**overrides) -> TutorContext:
    base = dict(grade_number=5, stage="middle", language="ru", mode="homework")
    base.update(overrides)
    return TutorContext(**base)


def test_history_maps_roles_and_starts_with_user():
    history = [
        {"role": "assistant", "content": "Давай начнём."},
        {"role": "user", "content": "Дай подсказку"},
        {"role": "user", "content": "Ещё одну"},
        {"role": "assistant", "content": ""},
    ]
    contents = history_to_contents(history, "Проверь ответ: 48")
    roles = [c.role for c in contents]
    assert roles == ["user", "model", "user", "user"]
    assert contents[0].parts[0].text  # synthetic opener before the model's first turn
    assert [p.text for p in contents[2].parts] == ["Дай подсказку", "Ещё одну"]  # merged same-role turns
    assert contents[-1].parts[0].text == "Проверь ответ: 48"


def test_respond_streams_visible_text_and_parses_meta(settings):
    settings.GEMINI_MODEL = "gemini-test"
    chunks = [
        _chunk("Сложи 10 и 2. "),
        _chunk("Что получилось? <me"),
        _chunk(
            'ta>{"check_question": "Сколько будет 10 + 2?", "answer_kind": "number", "expected_answer": "12"}</meta>',
            finish="STOP",
            usage=_usage(),
        ),
    ]
    provider = _provider(FakeModels(chunks=chunks))
    out = list(provider.respond(_context(history=[{"role": "user", "content": "Объясни"}]), "hint", ""))
    text = "".join(c.text for c in out if c.text)
    assert text.strip() == "Сложи 10 и 2. Что получилось?"
    assert "<meta>" not in text
    final = out[-1].final
    assert final is not None
    assert final.check_question == "Сколько будет 10 + 2?"
    assert final.expected_answer == "12"
    usage = out[-1].usage
    assert usage.input_tokens == 10
    assert usage.output_tokens == 25  # thinking tokens are billed as output
    assert usage.model == "gemini-test"


def test_respond_refusal_raises_domain_error(settings):
    settings.GEMINI_MODEL = "gemini-test"
    provider = _provider(FakeModels(chunks=[_chunk("", finish="SAFETY", usage=_usage())]))
    with pytest.raises(AIProviderError) as info:
        list(provider.respond(_context(), "hint", ""))
    assert info.value.code == "refused"
    assert info.value.usage is not None and info.value.usage.input_tokens == 10


def test_assess_converts_typed_criteria(settings):
    settings.GEMINI_MODEL = "gemini-test"
    parsed = GeminiAssessment(
        verdict="partial",
        confidence=0.7,
        feedback="Почти.",
        criteria=[{"name": "ответ", "met": False, "comment": "не хватает единиц"}],
        next_hint="Проверь единицы.",
    )
    response = SimpleNamespace(
        parsed=parsed, candidates=[], prompt_feedback=None, usage_metadata=_usage(), text=""
    )
    models = FakeModels(response=response)
    result, usage = _provider(models).assess(_context(), "46", ["верное число"], "48")
    assert result.verdict == "partial"
    assert result.criteria == [{"name": "ответ", "met": False, "comment": "не хватает единиц"}]
    assert usage.output_tokens == 25
    config = models.calls[0]["config"]
    assert config.response_schema is GeminiAssessment
    assert config.response_mime_type == "application/json"


def test_structured_rejects_unparsable_output(settings):
    settings.GEMINI_MODEL = "gemini-test"
    response = SimpleNamespace(
        parsed=None, candidates=[], prompt_feedback=None, usage_metadata=_usage(), text="{oops"
    )
    with pytest.raises(AIProviderError) as info:
        _provider(FakeModels(response=response)).assess(_context(), "46", [], "48")
    assert info.value.code == "invalid_output"
    assert info.value.retryable


def test_errors_are_mapped_to_domain_codes():
    rate = genai_errors.ClientError(429, {"error": {"message": "quota"}})
    assert _map_error(rate).code == "rate_limited"
    assert _map_error(rate).retryable
    assert _map_error(genai_errors.ClientError(403, {"error": {"message": "denied"}})).code == "auth"
    assert _map_error(genai_errors.ClientError(404, {"error": {"message": "no model"}})).code == "bad_request"
    server = _map_error(genai_errors.ServerError(503, {"error": {"message": "busy"}}))
    assert server.code == "http_503" and server.retryable
    assert _map_error(httpx.ReadTimeout("slow")).code == "timeout"
    assert _map_error(ValueError("x")).code == "unknown"


def test_usage_falls_back_to_requested_model_when_version_missing():
    usage = _usage_from(
        SimpleNamespace(usage_metadata=_usage(cached=4), model_version=""), "gemini-test", 0.0
    )
    assert usage.cache_read_tokens == 4
    assert usage.model == "gemini-test"


def test_recognition_bounds_one_attempt(settings):
    settings.GEMINI_MODEL_VISION = "gemini-vision-test"
    from ai.base import ImageInput, SubjectOption
    from ai.schemas import RecognitionResult

    parsed = RecognitionResult(readable=True, tasks=[])
    response = SimpleNamespace(
        parsed=parsed, candidates=[], prompt_feedback=None, usage_metadata=_usage(), text=""
    )
    models = FakeModels(response=response)
    _provider(models).recognize([ImageInput(b"jpg", "image/jpeg")], "", "ru", 5, [SubjectOption("math", "М")])
    config = models.calls[0]["config"]
    assert config.http_options.timeout == 12_000
    assert config.http_options.retry_options.attempts == 3
    assert models.calls[0]["model"] == "gemini-vision-test"
    assert len(models.calls[0]["contents"][0].parts) == 2  # image + prompt
