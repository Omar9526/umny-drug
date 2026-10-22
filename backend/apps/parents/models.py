from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class ParentNotification(UUIDModel, TimeStampedModel):
    class Kind(models.TextChoices):
        WEEKLY_REPORT = "weekly_report", "Недельный отчёт"
        DIFFICULT_TOPIC = "difficult_topic", "Сложная тема"
        SESSION_COMPLETED = "session_completed", "Задание выполнено"
        CONSENT = "consent", "Согласия"
        SYSTEM = "system", "Системное"

    parent = models.ForeignKey(
        "accounts.ParentProfile", on_delete=models.CASCADE, related_name="notifications"
    )
    student = models.ForeignKey(
        "accounts.StudentProfile",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["parent", "read_at", "-created_at"])]

    def __str__(self) -> str:
        return self.title
