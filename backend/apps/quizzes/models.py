from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.accounts.constants import LANGUAGE_CHOICES
from apps.core.models import TimeStampedModel, UUIDModel
from apps.curriculum.models import LocalizedNameMixin


class Quiz(LocalizedNameMixin, TimeStampedModel):
    topic = models.ForeignKey("curriculum.Topic", on_delete=models.CASCADE, related_name="quizzes")
    grade = models.ForeignKey("curriculum.Grade", on_delete=models.CASCADE, related_name="quizzes")
    description_ru = models.TextField(blank=True)
    description_ky = models.TextField(blank=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    is_active = models.BooleanField(default=True)

    class Source(models.TextChoices):
        ANTHROPIC = "anthropic", "Claude"
        GEMINI = "gemini", "Gemini"
        RULES = "rules", "Правила (арифметика)"
        MANUAL = "manual", "Составлена вручную"

    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    model = models.CharField(max_length=64, blank=True, help_text="Модель, составившая вопросы")

    class Meta:
        verbose_name = "викторина"
        verbose_name_plural = "викторины"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["topic", "language", "-created_at"])]


class Question(TimeStampedModel):
    class Type(models.TextChoices):
        SINGLE = "single", "Один ответ"
        MULTIPLE = "multiple", "Несколько ответов"
        NUMERIC = "numeric", "Числовой ответ"
        TEXT = "text", "Короткий текст"
        ORDERING = "ordering", "Расставь по порядку"
        MATCHING = "matching", "Соедини пары"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField(default=0)
    type = models.CharField(max_length=12, choices=Type.choices)
    prompt_ru = models.TextField()
    prompt_ky = models.TextField(blank=True)
    options = models.JSONField(default=list, blank=True, help_text="[{key, text_ru, text_ky}]")
    correct = models.JSONField(help_text="Ключ(и) правильного ответа, число, текст или порядок")
    tolerance = models.FloatField(default=0.0, help_text="Допуск для числовых ответов")
    explanation_ru = models.TextField(blank=True)
    explanation_ky = models.TextField(blank=True)
    hint_ru = models.CharField(max_length=300, blank=True)
    hint_ky = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [models.UniqueConstraint(fields=["quiz", "order"], name="uniq_question_order_per_quiz")]

    def __str__(self) -> str:
        return f"{self.quiz_id}/{self.order}: {self.prompt_ru[:40]}"

    def prompt(self, lang: str = "ru") -> str:
        return (self.prompt_ky if lang == "ky" and self.prompt_ky else self.prompt_ru) or self.prompt_ru

    def explanation(self, lang: str = "ru") -> str:
        value = self.explanation_ky if lang == "ky" and self.explanation_ky else self.explanation_ru
        return value or self.explanation_ru

    def hint(self, lang: str = "ru") -> str:
        return (self.hint_ky if lang == "ky" and self.hint_ky else self.hint_ru) or self.hint_ru

    def option_texts(self, lang: str = "ru") -> list[dict]:
        key = "text_ky" if lang == "ky" else "text_ru"
        return [{"key": o["key"], "text": o.get(key) or o.get("text_ru", "")} for o in self.options]


class QuizAttempt(UUIDModel, TimeStampedModel):
    class Mode(models.TextChoices):
        LEARNING = "learning", "Обучение (с объяснениями)"
        TEST = "test", "Проверка (ответы в конце)"

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "В процессе"
        FINISHED = "finished", "Завершена"
        ABANDONED = "abandoned", "Не завершена"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="quiz_attempts"
    )
    family = models.ForeignKey("accounts.Family", on_delete=models.CASCADE, related_name="quiz_attempts")
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.LEARNING)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)
    answers = models.JSONField(default=dict, blank=True, help_text="{question_id: answer}")
    results = models.JSONField(default=dict, blank=True, help_text="{question_id: {correct, explanation}}")
    correct_count = models.PositiveSmallIntegerField(default=0)
    total_count = models.PositiveSmallIntegerField(default=0)
    topics_to_review = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = [models.Index(fields=["student", "-started_at"])]

    def __str__(self) -> str:
        return f"Попытка {self.id} ({self.get_status_display()})"
