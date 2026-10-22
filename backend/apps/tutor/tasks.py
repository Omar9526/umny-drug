"""Operational tasks around the AI budget."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import mail_admins
from django.utils import timezone

from ai.costs import calls_today, spent_today_usd

logger = logging.getLogger("umnydrug.ai")


@shared_task(name="apps.tutor.tasks.check_ai_budget")
def check_ai_budget() -> str:
    """Warn the operators once a day when AI spend crosses ``AI_BUDGET_ALERT_THRESHOLD`` of the budget.

    The hard stop lives in ``ensure_budget``; this task gives people time to react before it fires.
    """
    budget = float(getattr(settings, "AI_DAILY_BUDGET_USD", 0) or 0)
    if budget <= 0:
        return "no-budget"
    spent = float(spent_today_usd())
    share = spent / budget
    threshold = float(getattr(settings, "AI_BUDGET_ALERT_THRESHOLD", 0.8) or 0.8)
    if share < threshold:
        return f"ok:{share:.2f}"
    today = timezone.localdate().isoformat()
    if not cache.add(f"ai-budget-alert:{today}", 1, timeout=60 * 60 * 36):
        return "already-alerted"
    calls = calls_today()
    if not settings.ADMINS:
        logger.error(
            "AI budget alert has no recipients: set DJANGO_ADMINS",
            extra={"event": "ai.budget_alert_unrouted"},
        )
    logger.warning(
        "AI budget at %d%% (%.2f of %.2f USD, %d calls)",
        round(share * 100),
        spent,
        budget,
        calls,
        extra={"event": "ai.budget_alert", "spent_usd": spent, "budget_usd": budget, "calls": calls},
    )
    mail_admins(
        subject=f"[Умный друг] Расход AI {share:.0%} дневного лимита",
        message=(
            f"За {today} потрачено ${spent:.2f} из ${budget:.2f} ({calls} вызовов). "
            f"При 100% новые запросы к модели будут отклоняться до конца дня."
        ),
        fail_silently=True,
    )
    return f"alerted:{share:.2f}"
