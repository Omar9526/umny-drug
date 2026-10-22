"""Upload → recognition → confirmation use-cases."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from ai.base import AIProviderError, ImageInput, SubjectOption
from ai.costs import ensure_budget, record_usage
from ai.registry import get_provider
from apps.accounts.models import StudentProfile
from apps.core.audit import audit
from apps.core.exceptions import DomainError
from apps.curriculum.models import Subject, Topic

from .images import ImageValidationError, for_model, process_upload
from .models import Assignment, AssignmentImage, AssignmentUpload

logger = logging.getLogger("umnydrug.assignments")

MIN_TYPED_TEXT = 3
MAX_TYPED_TEXT = 6000


class UploadError(DomainError):
    status_code = 400
    default_code = "upload_invalid"


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
@transaction.atomic
def create_upload(
    *,
    student: StudentProfile,
    source: str,
    files: Iterable,
    typed_text: str,
    language_hint: str,
    request=None,
) -> AssignmentUpload:
    files = list(files)
    typed_text = (typed_text or "").strip()
    if source == AssignmentUpload.Source.TEXT:
        if len(typed_text) < MIN_TYPED_TEXT:
            raise UploadError("Напиши условие задания: хотя бы несколько слов.", code="text_required")
        if len(typed_text) > MAX_TYPED_TEXT:
            raise UploadError("Текст слишком длинный. Раздели задание на части.", code="text_too_long")
        files = []
    else:
        if not files:
            raise UploadError("Добавь хотя бы одно фото задания.", code="images_required")
        if len(files) > settings.MAX_UPLOAD_IMAGES_PER_ASSIGNMENT:
            raise UploadError(
                f"Можно загрузить не больше {settings.MAX_UPLOAD_IMAGES_PER_ASSIGNMENT} фото за раз.",
                code="too_many_images",
            )

    upload = AssignmentUpload.objects.create(
        student=student,
        family=student.family,
        source=source,
        typed_text=typed_text,
        language_hint=language_hint or student.instruction_language,
    )
    for order, django_file in enumerate(files):
        try:
            processed = process_upload(django_file)
        except ImageValidationError as exc:
            raise UploadError(str(exc), code=exc.code)
        image = AssignmentImage(
            upload=upload,
            order=order,
            mime_type=processed.mime_type,
            width=processed.width,
            height=processed.height,
            size_bytes=processed.size_bytes,
            sha256=processed.sha256,
        )
        image.file.save(f"{image.sha256[:12]}.jpg", ContentFile(processed.data), save=True)

    audit(
        "assignment.uploaded",
        actor=student.user,
        target=upload,
        request=request,
        source=source,
        images=len(files),
    )
    return upload


def enqueue_recognition(upload: AssignmentUpload) -> None:
    """Hand the upload to the recognition task.

    With eager Celery (dev fallback / tests) the task runs inline right now; with a real broker it
    is queued after the surrounding transaction commits so the worker can see the rows.
    """
    from .tasks import recognize_upload_task

    if settings.CELERY_TASK_ALWAYS_EAGER:
        recognize_upload_task.delay(str(upload.id))
    else:
        transaction.on_commit(lambda: recognize_upload_task.delay(str(upload.id)))


# ---------------------------------------------------------------------------
# Recognition
# ---------------------------------------------------------------------------
def _subject_options(student: StudentProfile) -> list[SubjectOption]:
    grade_number = student.grade.number
    subjects = Subject.objects.filter(
        curriculum=student.curriculum,
        is_active=True,
        grade_from__lte=grade_number,
        grade_to__gte=grade_number,
    ).order_by("order")
    return [SubjectOption(slug=s.slug, name=s.name(student.explanation_language)) for s in subjects]


_WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ]{3,}")


def _tokens(text: str) -> set[str]:
    return {w.lower()[:6] for w in _WORD_RE.findall(text or "")}


def match_topic(subject: Subject | None, grade, text: str, hint: str | None) -> Topic | None:
    """Pick the catalogue topic whose keywords/name overlap most with the task text and the model hint."""
    if subject is None:
        return None
    haystack = _tokens(text) | _tokens(hint or "")
    if not haystack:
        return None
    best: tuple[int, Topic | None] = (0, None)
    topics = Topic.objects.filter(
        section__subject=subject, section__grade=grade, is_active=True
    ).select_related("section")
    for topic in topics:
        needles = _tokens(topic.name_ru) | _tokens(topic.name_ky) | {k.lower()[:6] for k in topic.keywords}
        score = len(haystack & needles)
        if hint and _tokens(hint) & _tokens(topic.name_ru):
            score += 2
        if score > best[0]:
            best = (score, topic)
    return best[1] if best[0] >= 2 else None


def _read_image(image: AssignmentImage) -> bytes:
    """Read and *close* the file: an open handle would block deletion later (Windows) and leak fds."""
    with image.file.open("rb") as handle:
        return handle.read()


def recognize_upload(upload_id: str) -> AssignmentUpload:
    """Run recognition for an upload. Safe to retry: a finished upload is returned untouched."""
    upload = AssignmentUpload.objects.select_related("student__grade", "student__curriculum", "family").get(
        id=upload_id
    )
    if upload.status in (AssignmentUpload.Status.RECOGNIZED, AssignmentUpload.Status.UNREADABLE):
        return upload
    # Conditional UPDATE: a second worker (Celery retry + manual retry) must not process it twice.
    claimed = AssignmentUpload.objects.filter(
        id=upload.id, status__in=[AssignmentUpload.Status.PENDING, AssignmentUpload.Status.FAILED]
    ).update(status=AssignmentUpload.Status.PROCESSING, updated_at=timezone.now())
    if not claimed:
        return upload
    upload.status = AssignmentUpload.Status.PROCESSING

    student = upload.student
    provider = get_provider()
    try:
        ensure_budget(student=student, family=upload.family)
        images = [
            ImageInput(data=for_model(_read_image(img)), mime_type="image/jpeg")
            for img in upload.images.filter(purged_at__isnull=True).order_by("order")
        ]
        result, usage = provider.recognize(
            images=images,
            typed_text=upload.typed_text,
            language=upload.language_hint,
            grade_number=student.grade.number,
            subjects=_subject_options(student),
        )
    except AIProviderError as exc:
        upload.status = AssignmentUpload.Status.FAILED
        upload.error_code = exc.code
        upload.error_message = str(exc)
        upload.provider = provider.name
        upload.demo_mode = provider.demo_mode
        upload.processed_at = timezone.now()
        upload.save()
        logger.warning("recognition failed: %s", exc.code, extra={"event": "ai.recognition_failed"})
        return upload
    except Exception:
        upload.status = AssignmentUpload.Status.FAILED
        upload.error_code = "internal"
        upload.error_message = "Не удалось обработать загрузку."
        upload.processed_at = timezone.now()
        upload.save()
        logger.exception("recognition crashed", extra={"event": "ai.recognition_crashed"})
        return upload

    record_usage(
        purpose="recognition", usage=usage, provider=provider.name, family=upload.family, student=student
    )
    with transaction.atomic():
        upload.provider = provider.name
        upload.model = usage.model
        upload.demo_mode = provider.demo_mode
        upload.input_tokens = usage.input_tokens
        upload.output_tokens = usage.output_tokens
        upload.cost_usd = usage.cost_usd
        upload.recognition = result.model_dump()
        upload.processed_at = timezone.now()
        if not result.readable or not result.tasks:
            upload.status = AssignmentUpload.Status.UNREADABLE
            upload.error_code = "unreadable"
            upload.error_message = (
                result.unreadable_reason
                or "Не удалось полностью прочитать задание. Попробуй сфотографировать его ещё раз при хорошем освещении."  # noqa: E501
            )
            upload.save()
            return upload

        subjects_by_slug = {s.slug: s for s in Subject.objects.filter(curriculum=student.curriculum)}
        for task in sorted(result.tasks, key=lambda t: t.index):
            subject = subjects_by_slug.get(task.subject_slug or "")
            if subject is not None and not subject.available_for(student.grade.number):
                subject = None
            topic = match_topic(subject, student.grade, task.text, task.topic_hint)
            Assignment.objects.create(
                student=student,
                family=upload.family,
                upload=upload,
                index_in_upload=task.index,
                label=task.label,
                recognized_text=task.text,
                grade=student.grade,
                subject=subject,
                topic=topic,
                detection={
                    "subject_slug": task.subject_slug,
                    "topic_hint": task.topic_hint,
                    "task_type": task.task_type,
                    "confidence": task.confidence,
                    "has_formula": task.has_formula,
                    "has_figure": task.has_figure,
                },
                language=task.language,
            )
        upload.status = AssignmentUpload.Status.RECOGNIZED
        upload.error_code = ""
        upload.error_message = ""
        upload.save()
    return upload


STALE_PROCESSING_MINUTES = 10


def retry_upload(upload: AssignmentUpload) -> AssignmentUpload:
    stale = (
        upload.status == AssignmentUpload.Status.PROCESSING
        and upload.updated_at < timezone.now() - timedelta(minutes=STALE_PROCESSING_MINUTES)
    )
    if upload.status != AssignmentUpload.Status.FAILED and not stale:
        raise DomainError(
            "Повторить можно только неудавшуюся загрузку.", code="not_retryable", status_code=409
        )
    upload.status = AssignmentUpload.Status.PENDING
    upload.error_code = ""
    upload.error_message = ""
    upload.save(update_fields=["status", "error_code", "error_message", "updated_at"])
    enqueue_recognition(upload)
    return upload


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------
@transaction.atomic
def confirm_assignment(
    *,
    assignment: Assignment,
    confirmed_text: str,
    subject: Subject | None,
    topic: Topic | None,
    subject_provided: bool = False,
    request=None,
):
    """Freeze the task text the child approved and open a tutoring session for it."""
    from apps.tutor.models import LearningSession
    from apps.tutor.services import create_session

    confirmed_text = confirmed_text.strip()
    if not confirmed_text:
        raise DomainError("Текст задания не может быть пустым.", code="validation_error", status_code=400)
    if assignment.status in (Assignment.Status.COMPLETED,):
        raise DomainError("Это задание уже выполнено.", code="already_completed", status_code=409)

    existing = (
        LearningSession.objects.filter(assignment=assignment, status=LearningSession.Status.ACTIVE)
        .order_by("-created_at")
        .first()
    )
    wanted_subject_id = (
        (topic.section.subject_id if topic is not None else subject.id) if (subject or topic) else None
    )
    same_subject = (not subject_provided) or wanted_subject_id == assignment.subject_id
    if existing is not None and assignment.text == confirmed_text and same_subject:
        return assignment, existing
    if existing is not None:
        # The child changed the task text: the old walk-through no longer applies.
        from apps.tutor.services import complete_session

        complete_session(session=existing, request=request, reason="reconfirmed")

    assignment.text_edited = confirmed_text != assignment.recognized_text
    assignment.confirmed_text = confirmed_text
    if subject_provided and subject is None and topic is None:
        assignment.subject = None  # the child explicitly removed the auto-detected subject
        assignment.topic = None
    if subject is not None:
        assignment.subject = subject
        if topic is not None and topic.section.subject_id != subject.id:
            topic = None
        assignment.topic = (
            topic if topic is not None else match_topic(subject, assignment.grade, confirmed_text, None)
        )
    elif topic is not None:
        assignment.topic = topic
        assignment.subject = topic.section.subject
    assignment.status = Assignment.Status.CONFIRMED
    assignment.confirmed_at = timezone.now()
    assignment.save()
    audit(
        "assignment.confirmed",
        actor=assignment.student.user,
        target=assignment,
        request=request,
        edited=assignment.text_edited,
    )

    session = create_session(
        student=assignment.student, mode=LearningSession.Mode.HOMEWORK, assignment=assignment, request=request
    )
    return assignment, session
