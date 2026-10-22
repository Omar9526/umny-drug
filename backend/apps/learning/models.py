from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel


def answer_image_path(instance: AnswerAttempt, filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()[:5]
    return f"answers/{instance.family_id}/{instance.session_id}/{uuid.uuid4().hex}.{ext}"


def default_answer_image_expiry():
    return timezone.now() + timedelta(days=settings.ASSIGNMENT_IMAGE_RETENTION_DAYS)


class AnswerAttempt(UUIDModel, TimeStampedModel):
    session = models.ForeignKey("tutor.LearningSession", on_delete=models.CASCADE, related_name="attempts")
    assignment = models.ForeignKey(
        "assignments.Assignment", null=True, blank=True, on_delete=models.SET_NULL, related_name="attempts"
    )
    student = models.ForeignKey("accounts.StudentProfile", on_delete=models.CASCADE, related_name="attempts")
    family = models.ForeignKey("accounts.Family", on_delete=models.CASCADE, related_name="attempts")
    attempt_number = models.PositiveSmallIntegerField(default=1)
    answer_text = models.TextField(blank=True)
    answer_image = models.FileField(upload_to=answer_image_path, max_length=255, null=True, blank=True)
    answer_image_expires_at = models.DateTimeField(null=True, blank=True)
    hints_before = models.PositiveSmallIntegerField(default=0)
    is_independent = models.BooleanField(default=True)

    class Meta:
        ordering = ("session", "attempt_number")
        indexes = [models.Index(fields=["student", "-created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "attempt_number"], name="uniq_attempt_number_per_session"
            )
        ]

    def __str__(self) -> str:
        return f"Попытка {self.attempt_number} ({self.session_id})"


class VerificationResult(UUIDModel, TimeStampedModel):
    class Method(models.TextChoices):
        SYMPY = "sympy", "Символьная проверка (SymPy)"
        NUMERIC = "numeric", "Числовое сравнение"
        EXACT = "exact", "Точное совпадение"
        RUBRIC = "rubric", "Оценка по критериям"
        MODEL = "model", "Оценка моделью"
        DEMO = "demo", "Демо-режим"

    class Verdict(models.TextChoices):
        CORRECT = "correct", "Верно"
        PARTIAL = "partial", "Частично верно"
        INCORRECT = "incorrect", "Неверно"
        UNCERTAIN = "uncertain", "Не удалось проверить уверенно"

    attempt = models.OneToOneField(AnswerAttempt, on_delete=models.CASCADE, related_name="verification")
    method = models.CharField(max_length=16, choices=Method.choices)
    verdict = models.CharField(max_length=16, choices=Verdict.choices)
    confidence = models.FloatField(default=0.0)
    feedback = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    provider = models.CharField(max_length=32, blank=True)
    model = models.CharField(max_length=64, blank=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    def __str__(self) -> str:
        return f"{self.get_verdict_display()} ({self.get_method_display()})"


class LearningProgress(UUIDModel, TimeStampedModel):
    """Per-topic learning state. Internal mastery is a float; the UI only ever shows the status."""

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Ещё не изучено"
        LEARNING = "learning", "Изучается"
        COMPLETED = "completed", "Выполнено"
        NEEDS_REVIEW = "needs_review", "Требуется повторение"
        MASTERED = "mastered", "Освоено"

    student = models.ForeignKey("accounts.StudentProfile", on_delete=models.CASCADE, related_name="progress")
    family = models.ForeignKey("accounts.Family", on_delete=models.CASCADE, related_name="progress")
    topic = models.ForeignKey("curriculum.Topic", on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.NOT_STARTED, db_index=True
    )
    sessions_count = models.PositiveIntegerField(default=0)
    attempts_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    independent_count = models.PositiveIntegerField(default=0)
    hints_count = models.PositiveIntegerField(default=0)
    mastery = models.FloatField(default=0.0)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "topic"], name="uniq_progress_student_topic")
        ]
        indexes = [models.Index(fields=["student", "status"])]

    def __str__(self) -> str:
        return f"{self.student_id} / {self.topic_id}: {self.get_status_display()}"


class KnowledgeMapNode(TimeStampedModel):
    """Placement of a topic on the visual «learning journey» for a subject and grade."""

    subject = models.ForeignKey("curriculum.Subject", on_delete=models.CASCADE, related_name="map_nodes")
    grade = models.ForeignKey("curriculum.Grade", on_delete=models.CASCADE, related_name="map_nodes")
    topic = models.OneToOneField("curriculum.Topic", on_delete=models.CASCADE, related_name="map_node")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    route_key = models.SlugField(max_length=48, db_index=True, help_text="Например math-5")
    order = models.PositiveSmallIntegerField(default=0)
    x = models.FloatField(default=50.0, help_text="Позиция по горизонтали, 0–100")
    y = models.FloatField(default=0.0, help_text="Позиция по вертикали, 0–100")
    icon = models.CharField(max_length=40, default="map-pin")

    class Meta:
        ordering = ("route_key", "order")
        constraints = [models.UniqueConstraint(fields=["route_key", "order"], name="uniq_map_node_order")]

    def __str__(self) -> str:
        return f"{self.route_key} #{self.order}: {self.topic.name_ru}"
