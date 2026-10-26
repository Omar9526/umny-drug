"""Parent cabinet: real aggregates, weekly reports, rule-based recommendations, consents, deletion.

Every number here is computed from stored sessions, attempts and progress rows. When there is not
enough data the API says so instead of inventing a figure.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.models import ConsentRecord, ParentProfile, StudentProfile
from apps.accounts.services import deactivate_child, revoke_user_sessions
from apps.assignments.models import Assignment, AssignmentImage, AssignmentUpload
from apps.core.audit import audit
from apps.core.exceptions import DomainError
from apps.learning.models import AnswerAttempt, LearningProgress
from apps.quizzes.models import QuizAttempt
from apps.tutor.models import LearningSession

from . import push
from .models import ParentNotification

logger = logging.getLogger("umnydrug.parents")

WEEK = timedelta(days=7)
Outcome = LearningSession.Outcome
Status = LearningSession.Status


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n_abs = abs(n) % 100
    last = n_abs % 10
    if 11 <= n_abs <= 19:
        return many
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def _subject_brief(subject, lang: str) -> dict | None:
    if subject is None:
        return None
    return {
        "id": subject.id,
        "slug": subject.slug,
        "name": subject.name(lang),
        "icon": subject.icon,
        "color": subject.color,
    }


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
def children_of(parent: ParentProfile):
    return (
        StudentProfile.objects.filter(family=parent.family, is_active=True)
        .select_related("grade", "curriculum", "user")
        .order_by("created_at")
    )


def child_for(parent: ParentProfile, child_id) -> StudentProfile:
    return get_object_or_404(children_of(parent), pk=child_id)


def child_for_erase(parent: ParentProfile, child_id) -> StudentProfile:
    """Erase must also reach a child that is already deactivated (DELETE or a revoked consent)."""
    return get_object_or_404(
        StudentProfile.objects.filter(family=parent.family).select_related("user"), pk=child_id
    )


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------
def child_summary(student: StudentProfile, now=None) -> dict:
    now = now or timezone.now()
    week_start = now - WEEK
    sessions = LearningSession.objects.filter(student=student)
    totals = sessions.aggregate(
        sessions_total=Count("id"),
        completed_total=Count("id", filter=Q(status=Status.COMPLETED)),
        sessions_week=Count("id", filter=Q(created_at__gte=week_start)),
        completed_week=Count("id", filter=Q(created_at__gte=week_start, status=Status.COMPLETED)),
        independent_week=Count(
            "id", filter=Q(created_at__gte=week_start, outcome=Outcome.UNDERSTOOD_INDEPENDENTLY)
        ),
        with_help_week=Count("id", filter=Q(created_at__gte=week_start, outcome=Outcome.COMPLETED_WITH_HELP)),
        needs_review_week=Count("id", filter=Q(created_at__gte=week_start, outcome=Outcome.NEEDS_REVIEW)),
        independent_total=Count("id", filter=Q(outcome=Outcome.UNDERSTOOD_INDEPENDENTLY)),
        last_activity_at=Max("last_activity_at"),
    )
    totals["quizzes_week"] = QuizAttempt.objects.filter(
        student=student, status=QuizAttempt.Status.FINISHED, finished_at__gte=week_start
    ).count()
    lang = student.explanation_language
    difficult = difficult_topics(student, limit=3)
    return {
        **totals,
        "difficult_topics": [
            {
                "topic_id": p.topic_id,
                "name": p.topic.name(lang),
                "status": p.status,
                "subject": _subject_brief(p.topic.section.subject, lang),
            }
            for p in difficult
        ],
    }


def difficult_topics(student: StudentProfile, limit: int = 5):
    """Topics that needed re-explanation: explicit «needs review», or repeated attempts without success."""
    qs = (
        LearningProgress.objects.filter(student=student)
        .filter(
            Q(status=LearningProgress.Status.NEEDS_REVIEW)
            | Q(status=LearningProgress.Status.LEARNING, hints_count__gte=2)
            | Q(status=LearningProgress.Status.LEARNING, attempts_count__gte=2, correct_count=0)
        )
        .select_related("topic__section__subject")
        .order_by("-last_activity_at")
    )
    return list(qs[:limit])


def subject_breakdown(student: StudentProfile) -> list[dict]:
    lang = student.explanation_language
    rows = (
        LearningSession.objects.filter(student=student, subject__isnull=False)
        .values("subject")
        .annotate(
            sessions=Count("id"),
            completed=Count("id", filter=Q(status=Status.COMPLETED)),
            independent=Count("id", filter=Q(outcome=Outcome.UNDERSTOOD_INDEPENDENTLY)),
            with_help=Count("id", filter=Q(outcome=Outcome.COMPLETED_WITH_HELP)),
            needs_review=Count("id", filter=Q(outcome=Outcome.NEEDS_REVIEW)),
            hints_avg=Avg("hints_used"),
            last_activity_at=Max("last_activity_at"),
        )
        .order_by("-last_activity_at")
    )
    subject_ids = [r["subject"] for r in rows]
    from apps.curriculum.models import Subject

    subjects = {s.id: s for s in Subject.objects.filter(id__in=subject_ids)}
    progress = (
        LearningProgress.objects.filter(student=student, topic__section__subject_id__in=subject_ids)
        .values("topic__section__subject_id", "status")
        .annotate(n=Count("id"))
    )
    topic_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in progress:
        topic_counts[row["topic__section__subject_id"]][row["status"]] += 1
    result = []
    for r in rows:
        subject = subjects.get(r["subject"])
        if subject is None:
            continue
        result.append(
            {
                "subject": _subject_brief(subject, lang),
                "sessions": r["sessions"],
                "completed": r["completed"],
                "independent": r["independent"],
                "with_help": r["with_help"],
                "needs_review": r["needs_review"],
                "hints_avg": round(r["hints_avg"] or 0, 1),
                "last_activity_at": r["last_activity_at"],
                "topics": dict(topic_counts.get(subject.id, {})),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Weekly report & recommendations (rule-based, data-backed)
# ---------------------------------------------------------------------------
def weekly_report(student: StudentProfile, now=None) -> dict:
    now = now or timezone.now()
    start = now - WEEK
    lang = student.explanation_language
    week = LearningSession.objects.filter(student=student, created_at__gte=start).select_related(
        "subject", "topic__section"
    )
    total = week.count()
    name = student.nickname
    if total == 0:
        return {
            "period_start": start,
            "period_end": now,
            "sessions": 0,
            "independent": 0,
            "with_help": 0,
            "needs_review": 0,
            "has_data": False,
            "text": f"{name}: на этой неделе не было занятий в приложении.",
            "highlights": [],
        }
    independent = week.filter(outcome=Outcome.UNDERSTOOD_INDEPENDENTLY).count()
    with_help = week.filter(outcome=Outcome.COMPLETED_WITH_HELP).count()
    needs_review = week.filter(outcome=Outcome.NEEDS_REVIEW).count()
    unfinished = total - independent - with_help - needs_review

    # Nicknames are not declined: «Алина на этой неделе: 3 задания», not «у Алина».
    parts = [f"{name} на этой неделе: {total} {plural_ru(total, 'задание', 'задания', 'заданий')}"]
    details = []
    if independent:
        details.append(f"{independent} {plural_ru(independent, 'решено', 'решены', 'решены')} самостоятельно")
    if with_help:
        details.append(f"{with_help} с подсказками")
    if needs_review:
        details.append(
            f"{needs_review} {plural_ru(needs_review, 'требует', 'требуют', 'требуют')} повторения"
        )
    if unfinished:
        details.append(f"{unfinished} не {plural_ru(unfinished, 'закончено', 'закончены', 'закончены')}")
    text = parts[0] + ". " + (", ".join(details).capitalize() + "." if details else "")
    text = text.strip()

    highlights: list[str] = []
    by_subject: dict[int, dict] = {}
    for s in week:
        if s.subject_id is None:
            continue
        row = by_subject.setdefault(s.subject_id, {"subject": s.subject, "total": 0, "independent": 0})
        row["total"] += 1
        if s.outcome == Outcome.UNDERSTOOD_INDEPENDENTLY:
            row["independent"] += 1
    strong = [r for r in by_subject.values() if r["total"] >= 2 and r["independent"] / r["total"] >= 0.6]
    for r in sorted(strong, key=lambda r: -r["independent"])[:2]:
        highlights.append(
            f"Большинство заданий по предмету «{r['subject'].name(lang)}» выполнено самостоятельно."
        )
    review_topics = {s.topic.name(lang) for s in week if s.outcome == Outcome.NEEDS_REVIEW and s.topic_id}
    for topic_name in sorted(review_topics)[:3]:
        highlights.append(f"По теме «{topic_name}» потребовались дополнительные объяснения.")
    return {
        "period_start": start,
        "period_end": now,
        "sessions": total,
        "independent": independent,
        "with_help": with_help,
        "needs_review": needs_review,
        "has_data": True,
        "text": " ".join([text, *highlights]),
        "highlights": highlights,
    }


def recommendations(student: StudentProfile, now=None) -> list[dict]:
    now = now or timezone.now()
    lang = student.explanation_language
    items: list[dict] = []
    sessions = LearningSession.objects.filter(student=student).select_related("subject", "topic")

    for progress in difficult_topics(student, limit=3):
        topic = progress.topic
        items.append(
            {
                "kind": "review_topic",
                "title": f"Повторить тему «{topic.name(lang)}»",
                "text": (
                    "Ребёнку понадобились подсказки или повторные попытки. "
                    "Короткое повторение закрепит материал."
                ),
                "action": {
                    "type": "explain_topic",
                    "topic_id": topic.id,
                    "subject_slug": topic.section.subject.slug,
                },
            }
        )

    covered_topics = {item["action"]["topic_id"] for item in items}
    week_review = sessions.filter(outcome=Outcome.NEEDS_REVIEW, created_at__gte=now - WEEK).order_by(
        "-ended_at"
    )
    for session in week_review:
        if session.topic_id and session.topic_id in covered_topics:
            continue
        label = session.title or (session.subject.name(lang) if session.subject_id else "задание")
        items.append(
            {
                "kind": "review_session",
                "title": f"Разобрать вместе: «{label}»",
                "text": (
                    "Задание не получилось решить самостоятельно. "
                    "Посмотрите разбор и попросите ребёнка попробовать ещё раз."
                ),
                "action": {"type": "session", "session_id": str(session.id)},
            }
        )
        if sum(1 for item in items if item["kind"] == "review_session") >= 2:
            break

    recent_completed = list(sessions.filter(status=Status.COMPLETED).order_by("-ended_at")[:5])
    if len(recent_completed) >= 3:
        revealed = sum(1 for s in recent_completed if s.solution_revealed)
        if revealed / len(recent_completed) >= 0.5:
            items.append(
                {
                    "kind": "too_many_reveals",
                    "title": "Часто просит показать решение",
                    "text": (
                        f"В {revealed} из {len(recent_completed)} последних заданий решение было раскрыто. "
                        "Предложите ребёнку сначала брать подсказку и пробовать самому."
                    ),
                    "action": None,
                }
            )
        if all(s.outcome == Outcome.UNDERSTOOD_INDEPENDENTLY for s in recent_completed[:3]):
            items.append(
                {
                    "kind": "doing_great",
                    "title": "Отлично справляется сам",
                    "text": (
                        "Три последних задания решены без подсказок. "
                        "Можно предложить задачи посложнее или тренировку."
                    ),
                    "action": None,
                }
            )

    last_activity = sessions.aggregate(last=Max("last_activity_at"))["last"]
    if last_activity and last_activity < now - WEEK:
        days = (now - last_activity).days
        items.append(
            {
                "kind": "inactive",
                "title": "Давно не было занятий",
                "text": (
                    f"Последнее занятие было {days} {plural_ru(days, 'день', 'дня', 'дней')} назад. "
                    "15 минут с фото домашней работы вернут ритм."
                ),
                "action": {"type": "photo"},
            }
        )

    for row in subject_breakdown(student):
        if row["sessions"] >= 3 and row["hints_avg"] >= 2:
            items.append(
                {
                    "kind": "subject_needs_support",
                    "title": f"{row['subject']['name']}: много подсказок",
                    "text": (
                        f"В среднем {row['hints_avg']} подсказки на задание. "
                        "Стоит разобрать базовые темы предмета."
                    ),
                    "action": {"type": "subject", "subject_slug": row["subject"]["slug"]},
                }
            )
    return items[:6]


def child_progress(student: StudentProfile) -> dict:
    now = timezone.now()
    lang = student.explanation_language
    recent = (
        LearningSession.objects.filter(student=student)
        .select_related("subject", "topic", "assignment")
        .order_by("-last_activity_at")[:5]
    )
    return {
        "summary": child_summary(student, now),
        "subjects": subject_breakdown(student),
        "difficult_topics": [
            {
                "topic_id": p.topic_id,
                "name": p.topic.name(lang),
                "status": p.status,
                "attempts_count": p.attempts_count,
                "hints_count": p.hints_count,
                "last_activity_at": p.last_activity_at,
                "subject": _subject_brief(p.topic.section.subject, lang),
            }
            for p in difficult_topics(student, limit=6)
        ],
        "weekly_report": weekly_report(student, now),
        "recommendations": recommendations(student, now),
        "recent_sessions": list(recent),
        "recent_quizzes": list(
            QuizAttempt.objects.filter(student=student, status=QuizAttempt.Status.FINISHED)
            .select_related("quiz__topic__section__subject")
            .order_by("-finished_at")[:5]
        ),
    }


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
def create_notification(**fields) -> ParentNotification:
    """Single entry point for parent notifications: the row plus a Web Push to the parent's devices."""
    notification = ParentNotification.objects.create(**fields)
    push.schedule(notification)
    return notification


def notify_parents(
    student: StudentProfile,
    *,
    kind: str,
    title: str,
    body: str,
    data: dict | None = None,
    dedupe_hours: int = 0,
):
    parents = list(student.family.parents.select_related("user"))
    created = []
    since = timezone.now() - timedelta(hours=dedupe_hours) if dedupe_hours else None
    for parent in parents:
        if (
            since
            and ParentNotification.objects.filter(
                parent=parent,
                student=student,
                kind=kind,
                created_at__gte=since,
                data__topic_id=(data or {}).get("topic_id"),
            ).exists()
        ):
            continue
        created.append(
            create_notification(
                parent=parent, student=student, kind=kind, title=title, body=body, data=data or {}
            )
        )
    return created


def notify_session_outcome(session: LearningSession) -> None:
    """Called when a session ends. Only «needs review» is pushed: it is the one parents must act on."""
    if session.outcome != Outcome.NEEDS_REVIEW:
        return
    student = session.student
    lang = student.explanation_language
    topic = session.topic.name(lang) if session.topic_id else None
    subject = session.subject.name(lang) if session.subject_id else None
    where = f"тема «{topic}»" if topic else (f"предмет «{subject}»" if subject else "задание")
    notify_parents(
        student,
        kind=ParentNotification.Kind.DIFFICULT_TOPIC,
        title=f"{student.nickname}: нужна помощь",
        body=f"Не получилось решить самостоятельно: {where}. Рекомендуем повторить вместе.",
        data={
            "session_id": str(session.id),
            "topic_id": session.topic_id,
            "subject_slug": session.subject.slug if session.subject_id else None,
        },
        dedupe_hours=24,
    )


def generate_weekly_reports(now=None) -> int:
    """Create one weekly-report notification per (parent, child) for the past 7 days. Idempotent per week."""
    now = now or timezone.now()
    created = 0
    for parent in ParentProfile.objects.filter(
        notify_weekly_report=True, user__is_active=True
    ).select_related("family"):
        for student in children_of(parent):
            if ParentNotification.objects.filter(
                parent=parent,
                student=student,
                kind=ParentNotification.Kind.WEEKLY_REPORT,
                created_at__gte=now - timedelta(days=6),
            ).exists():
                continue
            report = weekly_report(student, now)
            create_notification(
                parent=parent,
                student=student,
                kind=ParentNotification.Kind.WEEKLY_REPORT,
                title=f"Недельный отчёт: {student.nickname}",
                body=report["text"],
                data={k: v for k, v in report.items() if k not in ("period_start", "period_end", "text")},
            )
            created += 1
    return created


def mark_read(parent: ParentProfile, notification_id=None) -> int:
    qs = ParentNotification.objects.filter(parent=parent, read_at__isnull=True)
    if notification_id is not None:
        qs = qs.filter(pk=notification_id)
    return qs.update(read_at=timezone.now())


# ---------------------------------------------------------------------------
# Consents and deletion
# ---------------------------------------------------------------------------
NON_REVOCABLE_CONSENTS = (ConsentRecord.Type.TERMS, ConsentRecord.Type.PRIVACY)


@transaction.atomic
def revoke_consent(*, parent: ParentProfile, consent: ConsentRecord, request=None) -> ConsentRecord:
    if consent.consent_type in NON_REVOCABLE_CONSENTS:
        raise DomainError(
            "Это согласие нельзя отозвать отдельно: удалите семью, и аккаунт будет закрыт.",
            code="not_revocable",
            status_code=400,
        )
    if not consent.granted:
        return consent
    consent.revoke()
    audit(
        "consent.revoked",
        actor=parent.user,
        target=consent,
        request=request,
        consent_type=consent.consent_type,
    )
    if consent.student_id and consent.consent_type in (
        ConsentRecord.Type.CHILD_DATA,
        ConsentRecord.Type.AI_PROCESSING,
    ):
        student = consent.student
        if student.is_active:
            deactivate_child(parent=parent, student=student, request=request)
    return consent


@transaction.atomic
def _delete_stored_files(files: list[tuple[object, str]]) -> None:
    for storage, name in files:
        try:
            storage.delete(name)
        except OSError:
            logger.warning("could not delete stored file %s", name)


@transaction.atomic
def erase_child_data(*, parent: ParentProfile, student: StudentProfile, request=None) -> dict:
    """Delete learning data of a child now (not just deactivate). Audit rows stay without content.

    Files leave the storage only after the transaction commits, so a rollback never leaves rows
    that point at deleted files. ``Assignment`` rows are deleted explicitly: their upload FK is
    SET_NULL, so they would otherwise survive with the recognized text.
    """
    counts = {}
    files: list[tuple[object, str]] = []
    images = AssignmentImage.objects.filter(upload__student=student)
    counts["images"] = images.count()
    for image in images:
        if image.file:
            files.append((image.file.storage, image.file.name))
    for attempt in (
        AnswerAttempt.objects.filter(student=student)
        .exclude(answer_image__isnull=True)
        .exclude(answer_image="")
    ):
        files.append((attempt.answer_image.storage, attempt.answer_image.name))
    counts["uploads"] = AssignmentUpload.objects.filter(student=student).count()
    counts["assignments"] = Assignment.objects.filter(student=student).count()
    counts["sessions"] = LearningSession.objects.filter(student=student).count()
    LearningSession.objects.filter(student=student).delete()  # cascades conversation, messages, attempts
    Assignment.objects.filter(student=student).delete()
    AssignmentUpload.objects.filter(student=student).delete()  # cascades images
    LearningProgress.objects.filter(student=student).delete()
    QuizAttempt.objects.filter(student=student).delete()
    ParentNotification.objects.filter(student=student).delete()
    for consent in student.consents.filter(granted=True):
        consent.revoke()
    student.nickname = "Удалённый профиль"
    student.avatar = "fox"
    student.is_active = False
    student.deleted_at = timezone.now()
    student.save()
    student.user.display_name = "Удалённый профиль"
    student.user.is_active = False
    student.user.save(update_fields=["display_name", "is_active", "updated_at"])
    revoke_user_sessions(student.user)
    transaction.on_commit(lambda: _delete_stored_files(files))
    audit("child.data_erased", actor=parent.user, target=student, request=request, **counts)
    return counts


@transaction.atomic
def delete_family(*, parent: ParentProfile, password: str, request=None) -> dict:
    if not parent.user.check_password(password):
        raise DomainError("Неверный пароль.", code="invalid_credentials", status_code=403)
    erased = 0
    for student in StudentProfile.objects.filter(family=parent.family):
        erase_child_data(parent=parent, student=student, request=request)
        erased += 1
    for member in parent.family.parents.select_related("user"):
        member.user.is_active = False
        member.user.display_name = "Удалённый аккаунт"
        member.user.email = None
        member.user.save(update_fields=["is_active", "display_name", "email", "updated_at"])
        for consent in member.user.consents.filter(granted=True):
            consent.revoke()
        revoke_user_sessions(member.user)
    parent.family.rotate_code()
    audit("family.deleted", actor=parent.user, target=parent.family, request=request, children=erased)
    return {"children_erased": erased}
