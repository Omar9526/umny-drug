"""Subscription data model. Payment provider integration is out of MVP scope; no fake payments here."""

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel


class Subscription(UUIDModel, TimeStampedModel):
    class Plan(models.TextChoices):
        FREE = "free", "Бесплатный"
        FAMILY = "family", "Семейный"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        TRIAL = "trial", "Пробный период"
        PAST_DUE = "past_due", "Просрочена"
        CANCELED = "canceled", "Отменена"
        EXPIRED = "expired", "Истекла"

    family = models.OneToOneField("accounts.Family", on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.FREE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.family_id}: {self.get_plan_display()} ({self.get_status_display()})"


class Payment(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SUCCEEDED = "succeeded", "Оплачен"
        FAILED = "failed", "Ошибка"
        REFUNDED = "refunded", "Возврат"

    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="KGS")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=32, blank=True)
    external_id = models.CharField(max_length=128, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency} ({self.get_status_display()})"
