"""Shared querysets for learning sessions (student API and parent cabinet use the same shape)."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from apps.learning.models import AnswerAttempt

from .models import AIMessage, LearningSession


def session_queryset(*, detail: bool = False) -> QuerySet[LearningSession]:
    qs = LearningSession.objects.select_related(
        "student__user", "grade", "subject", "topic__section", "assignment__upload", "conversation", "family"
    )
    if detail:
        qs = qs.prefetch_related(
            "steps",
            Prefetch(
                "attempts",
                queryset=AnswerAttempt.objects.select_related("verification").order_by("attempt_number"),
            ),
            Prefetch(
                "conversation__messages",
                queryset=AIMessage.objects.exclude(role=AIMessage.Role.SYSTEM).order_by("created_at"),
            ),
        )
    return qs
