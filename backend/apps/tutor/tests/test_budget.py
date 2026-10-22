"""Budget guard, budget alert and the operators' usage summary."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from ai.base import AIProviderError
from ai.costs import ensure_budget
from apps.accounts.models import StudentProfile, User
from apps.accounts.tests.helpers import make_family
from apps.tutor.models import AIUsage
from apps.tutor.tasks import check_ai_budget

pytestmark = pytest.mark.django_db


def test_call_reservation_stops_parallel_requests_before_any_usage_row(settings):
    settings.AI_DAILY_CALLS_PER_STUDENT = 2
    cache.clear()
    fam = make_family()
    student = StudentProfile.objects.get(pk=fam["child"]["id"])
    ensure_budget(student=student, family=student.family)
    ensure_budget(student=student, family=student.family)
    with pytest.raises(AIProviderError) as info:  # no AIUsage row exists yet, the reservation alone stops it
        ensure_budget(student=student, family=student.family)
    assert info.value.code == "student_limit_exceeded"


def test_budget_alert_mails_admins_once_per_day(settings, mailoutbox):
    settings.AI_DAILY_BUDGET_USD = 10
    settings.AI_BUDGET_ALERT_THRESHOLD = 0.5
    settings.ADMINS = [("ops", "ops@example.com")]
    cache.clear()
    assert check_ai_budget().startswith("ok")
    AIUsage.objects.create(provider="gemini", model="m", purpose="tutor", cost_usd=Decimal("6"))
    assert check_ai_budget().startswith("alerted")
    assert len(mailoutbox) == 1
    assert "60%" in mailoutbox[0].subject
    assert check_ai_budget() == "already-alerted"
    assert len(mailoutbox) == 1


def test_usage_summary_is_for_admins_only():
    fam = make_family()
    assert fam["parent"].get("/api/v1/admin/ai-usage/").status_code == 403
    assert fam["student"].get("/api/v1/admin/ai-usage/").status_code == 403
    family = StudentProfile.objects.get(pk=fam["child"]["id"]).family
    AIUsage.objects.create(
        provider="gemini", model="m", purpose="quiz", cost_usd=Decimal("0.5"), family=family
    )
    admin = User.objects.create_superuser(email="root@example.com", password="Strong-pass-123")
    client = APIClient()
    client.force_authenticate(admin)
    body = client.get("/api/v1/admin/ai-usage/").json()
    assert body["today"]["calls"] == 1
    assert body["today"]["cost_usd"] == 0.5
    assert body["by_purpose_today"][0]["purpose"] == "quiz"
    assert body["top_families_today"][0]["family_id"] == str(family.id)
    assert "prompt" not in str(body)
