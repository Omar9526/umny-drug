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


class PushSubscription(UUIDModel, TimeStampedModel):
    """A browser or installed PWA of a parent that agreed to receive Web Push.

    One row per push endpoint. The endpoint is unique: a shared phone re-subscribed by another parent
    moves to that parent (see ``push.subscribe``). Keys are the browser's ECDH public key and auth secret
    needed to encrypt payloads for this device only.
    """

    parent = models.ForeignKey(
        "accounts.ParentProfile", on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=200, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Push-подписка {self.parent_id}"

    @property
    def subscription_info(self) -> dict:
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}
