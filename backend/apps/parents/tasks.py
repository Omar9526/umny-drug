from celery import shared_task


@shared_task(name="apps.parents.tasks.send_weekly_reports")
def send_weekly_reports() -> int:
    """Weekly report notifications for every parent who opted in (Celery beat, Monday morning)."""
    from .services import generate_weekly_reports

    return generate_weekly_reports()
