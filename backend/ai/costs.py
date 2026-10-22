"""Token accounting, cost estimation and the daily budget guard.

Prices are USD per million tokens and come from ``AI_PRICING_JSON`` (env) with sensible defaults
for the current Claude and Gemini generations. Unknown models cost 0 and are flagged in ``cost_known``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .base import AIProviderError, Usage

DEFAULT_PRICING = {
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.20, "cache_write": 5.0},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.20, "cache_write": 2.5},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125},
    # Gemini 3.8 Flash: introductory rate until 2026-12-31; from 2027-01-01 Google doubles it
    # (1.50 / 7.50 / 0.15). Override via AI_PRICING_JSON when that happens.
    "gemini-3.8-flash": {"input": 0.75, "output": 3.75, "cache_read": 0.075, "cache_write": 0.0},
    "gemini-3.5-flash": {"input": 1.50, "output": 9.0, "cache_read": 0.15, "cache_write": 0.0},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50, "cache_read": 0.03, "cache_write": 0.0},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cache_read": 0.03, "cache_write": 0.0},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0, "cache_read": 0.125, "cache_write": 0.0},
}


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float
    cache_write: float


def pricing_table() -> dict[str, Price]:
    table = dict(DEFAULT_PRICING)
    raw = getattr(settings, "AI_PRICING_JSON", "") or ""
    if raw:
        try:
            table.update(json.loads(raw))
        except json.JSONDecodeError as exc:  # pragma: no cover - configuration error
            raise RuntimeError("AI_PRICING_JSON is not valid JSON") from exc
    return {model: Price(**values) for model, values in table.items()}


def estimate_cost(model: str, usage: Usage) -> float:
    price = pricing_table().get(model)
    if price is None:
        return 0.0
    per_token = 1 / 1_000_000
    return round(
        usage.input_tokens * price.input * per_token
        + usage.output_tokens * price.output * per_token
        + usage.cache_read_tokens * price.cache_read * per_token
        + usage.cache_write_tokens * price.cache_write * per_token,
        6,
    )


def _day_start():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def spent_today_usd(**filters) -> Decimal:
    from apps.tutor.models import AIUsage

    total = AIUsage.objects.filter(created_at__gte=_day_start(), **filters).aggregate(total=Sum("cost_usd"))[
        "total"
    ]
    return total or Decimal("0")


def calls_today(**filters) -> int:
    from apps.tutor.models import AIUsage

    return AIUsage.objects.filter(created_at__gte=_day_start(), **filters).count()


def ensure_budget(*, student=None, family=None) -> None:
    """Refuse new AI work once today's recorded spend reaches a limit.

    Three independent caps: the global daily budget, a per-family daily budget (one family cannot
    exhaust the service for everyone) and a per-student call count (a runaway client is stopped
    even when prices are unknown and cost is recorded as 0).
    """
    budget = float(getattr(settings, "AI_DAILY_BUDGET_USD", 0) or 0)
    if budget > 0 and float(spent_today_usd()) >= budget:
        raise AIProviderError(
            "Дневной лимит AI-запросов сервиса исчерпан. Попробуй завтра.",
            code="budget_exceeded",
        )
    family_budget = float(getattr(settings, "AI_DAILY_BUDGET_PER_FAMILY_USD", 0) or 0)
    if family is not None and family_budget > 0 and float(spent_today_usd(family=family)) >= family_budget:
        raise AIProviderError(
            "Дневной лимит AI-запросов для вашей семьи исчерпан. Продолжим завтра.",
            code="family_budget_exceeded",
        )
    max_calls = int(getattr(settings, "AI_DAILY_CALLS_PER_STUDENT", 0) or 0)
    if student is not None and max_calls > 0 and calls_today(student=student) >= max_calls:
        raise AIProviderError(
            "На сегодня запросов к помощнику достаточно. Отдохни и возвращайся завтра.",
            code="student_limit_exceeded",
        )


def record_usage(*, purpose: str, usage: Usage, provider: str, family=None, student=None, session=None):
    from apps.tutor.models import AIUsage

    return AIUsage.objects.create(
        family=family,
        student=student,
        session=session,
        provider=provider,
        model=usage.model,
        purpose=purpose,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        cost_usd=Decimal(str(usage.cost_usd)),
        latency_ms=usage.latency_ms,
    )
