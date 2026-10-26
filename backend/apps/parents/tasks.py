from celery import shared_task


@shared_task(name="apps.parents.tasks.send_weekly_reports")
def send_weekly_reports() -> int:
    """Weekly report notifications for every parent who opted in (Celery beat, Monday morning)."""
    from .services import generate_weekly_reports

    return generate_weekly_reports()


@shared_task(name="apps.parents.tasks.send_push")
def send_push(notification_id: str) -> dict:
    """Deliver one parent notification to the parent's push-subscribed devices (queued on commit)."""
    from . import push
    from .models import ParentNotification

    notification = ParentNotification.objects.filter(pk=notification_id).first()
    if notification is None:
        return {"skipped": 1}
    return push.deliver(notification)
