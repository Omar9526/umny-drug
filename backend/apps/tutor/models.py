from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.accounts.constants import LANGUAGE_CHOICES
from apps.core.models import TimeStampedModel, UUIDModel


class LearningSession(UUIDModel, TimeStampedModel):
    """One sitting with the tutor: an assignment walk-through, a free question or a topic review."""

    class Mode(models.TextChoices):
        HOMEWORK = "homework", "Помощь с заданием"
        QUESTION = "question", "Вопрос"
        EXPLAIN_TOPIC = "explain_topic", "Объяснение темы"
        CHECK_ANSWER = "check_answer", "Проверка ответа"
        EXAM_PREP = "exam_prep", "Подготовка к контрольной"
        PRACTICE = "practice", "Тренировка"

    class Status(models.TextChoices):
        ACTIVE = "active", "Разбираемся"
        COMPLETED = "completed", "Выполнено"
        ABANDONED = "abandoned", "Не завершено"

    class Outcome(models.TextChoices):
        UNDERSTOOD_INDEPENDENTLY = "independent", "Решил самостоятельно"
        COMPLETED_WITH_HELP = "with_help", "Выполнил с подсказками"
        NEEDS_REVIEW = "needs_review", "Требуется повторение"
        NOT_COMPLETED = "not_completed", "Не завершено"

    student = models.ForeignKey("accounts.StudentProfile", on_delete=models.CASCADE, related_name="sessions")
    family = models.ForeignKey("accounts.Family", on_delete=models.CASCADE, related_name="sessions")
    assignment = models.ForeignKey(
        "assignments.Assignment", null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions"
    )
    grade = models.ForeignKey("curriculum.Grade", on_delete=models.PROTECT, related_name="sessions")
    subject = models.ForeignKey(
        "curriculum.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions"
    )
    topic = models.ForeignKey(
        "curriculum.Topic", null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions"
    )
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.HOMEWORK)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    outcome = models.CharField(max_length=16, choices=Outcome.choices, blank=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    title = models.CharField(max_length=160, blank=True)
    hints_used = models.PositiveSmallIntegerField(default=0)
    explanations_count = models.PositiveSmallIntegerField(default=0)
    attempts_count = models.PositiveSmallIntegerField(default=0)
    correct_attempts = models.PositiveSmallIntegerField(default=0)
    solution_revealed = models.BooleanField(default=False)
    understood_points = models.JSONField(default=list, blank=True)
    mistakes_fixed = models.JSONField(default=list, blank=True)
    summary_for_parent = models.TextField(blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-last_activity_at",)
        indexes = [
            models.Index(fields=["student", "status", "-last_activity_at"]),
            models.Index(fields=["family", "-last_activity_at"]),
        ]

    def __str__(self) -> str:
        return self.title or f"Сессия {self.id}"

    def touch(self) -> None:
        self.last_activity_at = timezone.now()

    @property
    def is_independent(self) -> bool:
        return self.correct_attempts > 0 and self.hints_used == 0 and not self.solution_revealed


class AIConversation(UUIDModel, TimeStampedModel):
    session = models.OneToOneField(LearningSession, on_delete=models.CASCADE, related_name="conversation")
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=64, blank=True)
    demo_mode = models.BooleanField(default=False)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    def __str__(self) -> str:
        return f"Диалог {self.session_id} ({self.provider})"


class AIMessage(UUIDModel):
    class Role(models.TextChoices):
        USER = "user", "Ученик"
        ASSISTANT = "assistant", "Помощник"
        SYSTEM = "system", "Система"

    class Command(models.TextChoices):
        NONE = "", "—"
        START = "start", "Начать разбор"
        SIMPLER = "simpler", "Объясни проще"
        EXAMPLE = "example", "Покажи пример"
        WHY = "why", "Почему так?"
        HINT = "hint", "Дай подсказку"
        CHECK = "check", "Проверь ответ"
        REPEAT = "repeat", "Объясни ещё раз"
        DONT_UNDERSTAND = "dont_understand", "Я не понял"
        SIMILAR = "similar", "Похожая задача"
        NEXT_STEP = "next_step", "Следующий шаг"

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=12, choices=Role.choices)
    command = models.CharField(max_length=24, choices=Command.choices, blank=True, default="")
    content = models.TextField()
    payload = models.JSONField(default=dict, blank=True, help_text="Структурированный ответ модели")
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    flagged = models.BooleanField(default=False, help_text="Ученик отметил ответ как неверный")
    flag_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"{self.get_role_display()}: {self.content[:40]}"


class SolutionStep(UUIDModel):
    session = models.ForeignKey(LearningSession, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=160)
    content = models.TextField()
    is_hint = models.BooleanField(default=False)
    revealed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("session", "order")
        constraints = [
            models.UniqueConstraint(fields=["session", "order"], name="uniq_step_order_per_session")
        ]

    def __str__(self) -> str:
        return f"Шаг {self.order}: {self.title}"


class AIUsage(UUIDModel):
    """One row per model call: the source of truth for cost monitoring and the daily budget guard."""

    class Purpose(models.TextChoices):
        RECOGNITION = "recognition", "Распознавание"
        TUTOR = "tutor", "Объяснение"
        ASSESS = "assess", "Проверка ответа"
        QUIZ = "quiz", "Проверка по теме"

    family = models.ForeignKey(
        "accounts.Family", null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_usage"
    )
    student = models.ForeignKey(
        "accounts.StudentProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_usage"
    )
    session = models.ForeignKey(
        LearningSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="ai_usage"
    )
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=64, blank=True)
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cache_read_tokens = models.PositiveIntegerField(default=0)
    cache_write_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["created_at", "purpose"])]

    def __str__(self) -> str:
        return f"{self.purpose} {self.model} ${self.cost_usd}"
