"""Learning progress bookkeeping. Status, not points: the UI never shows the internal mastery float."""

from __future__ import annotations

from collections import Counter

from django.db import transaction
from django.utils import timezone

from apps.curriculum.models import Grade, Subject, Topic
from apps.tutor.models import LearningSession

from .models import KnowledgeMapNode, LearningProgress

MASTERED_INDEPENDENT_SESSIONS = 2
QUIZ_PASS_SCORE = 0.8
QUIZ_REVIEW_SCORE = 0.5


@transaction.atomic
def apply_session_result(session: LearningSession) -> LearningProgress | None:
    """Fold a finished session into the per-topic progress row."""
    if session.topic_id is None:
        return None
    progress, _ = LearningProgress.objects.select_for_update().get_or_create(
        student=session.student, topic_id=session.topic_id, defaults={"family": session.family}
    )
    progress.sessions_count += 1
    progress.attempts_count += session.attempts_count
    progress.correct_count += session.correct_attempts
    progress.hints_count += session.hints_used
    independent = session.outcome == LearningSession.Outcome.UNDERSTOOD_INDEPENDENTLY
    if independent:
        progress.independent_count += 1

    if session.outcome == LearningSession.Outcome.NEEDS_REVIEW:
        progress.status = LearningProgress.Status.NEEDS_REVIEW
    elif independent and progress.independent_count >= MASTERED_INDEPENDENT_SESSIONS:
        progress.status = LearningProgress.Status.MASTERED
    elif session.outcome in (
        LearningSession.Outcome.UNDERSTOOD_INDEPENDENTLY,
        LearningSession.Outcome.COMPLETED_WITH_HELP,
    ):
        progress.status = LearningProgress.Status.COMPLETED
    else:
        progress.status = LearningProgress.Status.LEARNING

    total = max(progress.attempts_count, 1)
    accuracy = progress.correct_count / total
    hint_penalty = min(progress.hints_count / (progress.sessions_count * 3 or 1), 1.0) * 0.3
    progress.mastery = round(
        max(0.0, min(1.0, accuracy * 0.7 + (0.3 if independent else 0.1) - hint_penalty)), 3
    )
    progress.last_activity_at = timezone.now()
    progress.save()
    return progress


def mark_topic_learning(session: LearningSession) -> None:
    """A topic becomes «изучается» as soon as the child opens a session on it."""
    if session.topic_id is None:
        return
    LearningProgress.objects.get_or_create(
        student=session.student,
        topic_id=session.topic_id,
        defaults={
            "family": session.family,
            "status": LearningProgress.Status.LEARNING,
            "last_activity_at": timezone.now(),
        },
    )


@transaction.atomic
def apply_quiz_result(attempt, score: float) -> LearningProgress:
    """A finished self-check moves the topic status; it never awards points."""
    status = LearningProgress.Status
    progress, _ = LearningProgress.objects.select_for_update().get_or_create(
        student=attempt.student, topic_id=attempt.quiz.topic_id, defaults={"family": attempt.family}
    )
    if score >= QUIZ_PASS_SCORE:
        progress.status = (
            status.MASTERED if progress.status in (status.COMPLETED, status.MASTERED) else status.COMPLETED
        )
    elif score < QUIZ_REVIEW_SCORE:
        progress.status = status.NEEDS_REVIEW
    elif progress.status == status.MASTERED:
        progress.status = status.COMPLETED
    elif progress.status != status.COMPLETED:
        progress.status = status.LEARNING
    progress.mastery = round(max(0.0, min(1.0, progress.mastery * 0.5 + score * 0.5)), 3)
    progress.last_activity_at = timezone.now()
    progress.save()
    return progress


def _route_topics(subject: Subject, grade: Grade) -> list[tuple[KnowledgeMapNode | None, Topic]]:
    nodes = list(
        KnowledgeMapNode.objects.filter(route_key=f"{subject.slug}-{grade.number}", topic__is_active=True)
        .select_related("topic__section")
        .order_by("order")
    )
    if nodes:
        return [(node, node.topic) for node in nodes]
    topics = list(
        Topic.objects.filter(section__subject=subject, section__grade=grade, is_active=True)
        .select_related("section")
        .order_by("section__order", "order")
    )
    return [(None, topic) for topic in topics]


def knowledge_map(*, student, subject: Subject, grade: Grade, lang: str) -> dict:
    """The child's route through one subject: every topic with its honest status, and the next step."""
    from apps.quizzes.models import QuizAttempt

    pairs = _route_topics(subject, grade)
    topic_ids = [topic.id for _, topic in pairs]
    progress = {
        p.topic_id: p for p in LearningProgress.objects.filter(student=student, topic_id__in=topic_ids)
    }
    last_quiz: dict[int, dict] = {}
    for row in (
        QuizAttempt.objects.filter(
            student=student, status=QuizAttempt.Status.FINISHED, quiz__topic_id__in=topic_ids
        )
        .order_by("quiz__topic_id", "-finished_at")
        .values("quiz__topic_id", "correct_count", "total_count", "finished_at")
    ):
        last_quiz.setdefault(
            row["quiz__topic_id"],
            {
                "correct_count": row["correct_count"],
                "total_count": row["total_count"],
                "score": round(row["correct_count"] / row["total_count"], 3) if row["total_count"] else 0.0,
                "finished_at": row["finished_at"],
            },
        )

    zigzag = (50, 76, 80, 59, 30, 18, 32, 61)
    nodes = []
    for index, (node, topic) in enumerate(pairs):
        row = progress.get(topic.id)
        nodes.append(
            {
                "topic_id": topic.id,
                "slug": topic.slug,
                "name": topic.name(lang),
                "section": {"id": topic.section_id, "name": topic.section.name(lang)},
                "order": index,
                "x": node.x if node else zigzag[index % len(zigzag)],
                "icon": node.icon if node else "map-pin",
                "difficulty": topic.difficulty,
                "status": row.status if row else LearningProgress.Status.NOT_STARTED,
                "sessions_count": row.sessions_count if row else 0,
                "last_activity_at": row.last_activity_at if row else None,
                "last_quiz": last_quiz.get(topic.id),
            }
        )

    counts = Counter(n["status"] for n in nodes)
    next_topic = None
    for wanted in (
        LearningProgress.Status.NEEDS_REVIEW,
        LearningProgress.Status.LEARNING,
        LearningProgress.Status.NOT_STARTED,
    ):
        next_topic = next((n for n in nodes if n["status"] == wanted), None)
        if next_topic is not None:
            break
    return {
        "subject": {
            "id": subject.id,
            "slug": subject.slug,
            "name": subject.name(lang),
            "icon": subject.icon,
            "color": subject.color,
            "strategy": subject.strategy,
        },
        "grade": {"id": grade.id, "number": grade.number},
        "nodes": nodes,
        "summary": {
            "total": len(nodes),
            "not_started": counts.get(LearningProgress.Status.NOT_STARTED, 0),
            "learning": counts.get(LearningProgress.Status.LEARNING, 0),
            "completed": counts.get(LearningProgress.Status.COMPLETED, 0),
            "needs_review": counts.get(LearningProgress.Status.NEEDS_REVIEW, 0),
            "mastered": counts.get(LearningProgress.Status.MASTERED, 0),
        },
        "next_topic_id": next_topic["topic_id"] if next_topic else None,
    }
