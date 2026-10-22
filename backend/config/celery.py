import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("umnydrug")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "purge-expired-assignment-images": {
        "task": "apps.assignments.tasks.purge_expired_images",
        "schedule": 60 * 60 * 6,
    },
    "send-weekly-parent-reports": {
        "task": "apps.parents.tasks.send_weekly_reports",
        "schedule": crontab(day_of_week="monday", hour=9, minute=0),
    },
}
