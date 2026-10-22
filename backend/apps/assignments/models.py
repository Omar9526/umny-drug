from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.constants import LANGUAGE_CHOICES
from apps.core.models import TimeStampedModel, UUIDModel


def assignment_image_path(instance: AssignmentImage, filename: str) -> str:
    """Opaque, non-guessable storage key; original file names are never kept."""
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()[:5]
    return f"assignments/{instance.upload.family_id}/{instance.upload_id}/{uuid.uuid4().hex}.{ext}"


def default_image_expiry():
    return timezone.now() + timedelta(days=settings.ASSIGNMENT_IMAGE_RETENTION_DAYS)


class AssignmentUpload(UUIDModel, TimeStampedModel):
    """One act of «sharing homework»: a photo set or typed text that recognition splits into tasks."""

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает обработки"
        PROCESSING = "processing", "Распознаётся"
        RECOGNIZED = "recognized", "Распознано"
        UNREADABLE = "unreadable", "Не удалось прочитать"
        FAILED = "failed", "Ошибка"

    class Source(models.TextChoices):
        CAMERA = "camera", "Камера"
        GALLERY = "gallery", "Галерея"
        TEXT = "text", "Введено вручную"

    student = models.ForeignKey("accounts.StudentProfile", on_delete=models.CASCADE, related_name="uploads")
    family = models.ForeignKey("accounts.Family", on_delete=models.CASCADE, related_name="uploads")
    source = models.CharField(max_length=16, choices=Source.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    typed_text = models.TextField(blank=True)
    language_hint = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    recognition = models.JSONField(
        default=dict, blank=True, help_text="Валидированный результат распознавания"
    )
    error_code = models.CharField(max_length=48, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    provider = models.CharField(max_length=32, blank=True)
    model = models.CharField(max_length=64, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    demo_mode = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["student", "-created_at"])]

    def __str__(self) -> str:
        return f"Загрузка {self.id} ({self.get_status_display()})"


class AssignmentImage(UUIDModel, TimeStampedModel):
    upload = models.ForeignKey(AssignmentUpload, on_delete=models.CASCADE, related_name="images")
    file = models.FileField(upload_to=assignment_image_path, max_length=255)
    order = models.PositiveSmallIntegerField(default=0)
    mime_type = models.CharField(max_length=32)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    size_bytes = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField(default=default_image_expiry, db_index=True)
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("upload", "order")

    def __str__(self) -> str:
        return f"Изображение {self.order + 1} загрузки {self.upload_id}"

    @property
    def is_available(self) -> bool:
        return self.purged_at is None and bool(self.file)


class Assignment(UUIDModel, TimeStampedModel):
    """A single task the child chose to work on (one upload may contain several)."""

    class Status(models.TextChoices):
        RECOGNIZED = "recognized", "Распознано"
        CONFIRMED = "confirmed", "Условие подтверждено"
        IN_PROGRESS = "in_progress", "Разбираемся"
        COMPLETED = "completed", "Выполнено"
        NEEDS_REVIEW = "needs_review", "Требуется повторение"
        ABANDONED = "abandoned", "Не завершено"

    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="assignments"
    )
    family = models.ForeignKey("accounts.Family", on_delete=models.CASCADE, related_name="assignments")
    upload = models.ForeignKey(
        AssignmentUpload, null=True, blank=True, on_delete=models.SET_NULL, related_name="assignments"
    )
    index_in_upload = models.PositiveSmallIntegerField(default=0)
    label = models.CharField(max_length=40, blank=True, help_text="Например «№ 3» или «Упражнение 12»")
    recognized_text = models.TextField()
    confirmed_text = models.TextField(blank=True)
    text_edited = models.BooleanField(default=False)
    grade = models.ForeignKey("curriculum.Grade", on_delete=models.PROTECT, related_name="assignments")
    subject = models.ForeignKey(
        "curriculum.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="assignments"
    )
    topic = models.ForeignKey(
        "curriculum.Topic", null=True, blank=True, on_delete=models.SET_NULL, related_name="assignments"
    )
    detection = models.JSONField(
        default=dict, blank=True, help_text="Что определила модель: предмет, тема, тип задания, уверенность"
    )
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECOGNIZED, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["student", "status", "-created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["upload", "index_in_upload"],
                condition=models.Q(upload__isnull=False),
                name="uniq_task_index_per_upload",
            )
        ]

    def __str__(self) -> str:
        return f"Задание {self.label or self.id} ({self.get_status_display()})"

    @property
    def text(self) -> str:
        return self.confirmed_text or self.recognized_text
