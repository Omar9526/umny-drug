import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("umnydrug.assignments")


@shared_task(
    name="apps.assignments.tasks.recognize_upload_task",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def recognize_upload_task(self, upload_id: str) -> str:
    from .models import AssignmentUpload
    from .services import recognize_upload

    upload = recognize_upload(upload_id)
    if upload.status == AssignmentUpload.Status.FAILED and upload.error_code in {
        "rate_limited",
        "timeout",
        "connection",
        "http_500",
        "http_502",
        "http_503",
        "http_529",
    }:
        # Transient provider failure: put it back to pending and retry with backoff.
        if self.request.retries < self.max_retries:
            AssignmentUpload.objects.filter(id=upload.id).update(status=AssignmentUpload.Status.PENDING)
            raise self.retry(countdown=5 * (self.request.retries + 1))
    return upload.status


@shared_task(name="apps.assignments.tasks.purge_expired_images")
def purge_expired_images() -> int:
    """Delete image files whose retention window passed. Rows stay (without files) for history."""
    from apps.learning.models import AnswerAttempt

    from .models import AssignmentImage

    now = timezone.now()
    purged = 0
    for image in AssignmentImage.objects.filter(expires_at__lte=now, purged_at__isnull=True).iterator():
        try:
            if image.file:
                image.file.delete(save=False)
        except OSError:
            logger.warning(
                "could not delete image %s, will retry", image.id, extra={"event": "retention.delete_failed"}
            )
            continue
        image.purged_at = now
        image.save(update_fields=["purged_at", "updated_at"])
        purged += 1
    for attempt in AnswerAttempt.objects.filter(
        answer_image__isnull=False, answer_image_expires_at__lte=now
    ).exclude(answer_image=""):
        try:
            attempt.answer_image.delete(save=False)
        except OSError:
            logger.warning(
                "could not delete answer image %s, will retry",
                attempt.id,
                extra={"event": "retention.delete_failed"},
            )
            continue
        attempt.answer_image = None
        attempt.save(update_fields=["answer_image", "updated_at"])
        purged += 1
    if purged:
        logger.info("purged %s expired images", purged, extra={"event": "retention.purged"})
    return purged
