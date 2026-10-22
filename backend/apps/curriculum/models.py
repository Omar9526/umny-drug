from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class LocalizedNameMixin(models.Model):
    name_ru = models.CharField(max_length=160)
    name_ky = models.CharField(max_length=160, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.name_ru

    def name(self, lang: str = "ru") -> str:
        if lang == "ky" and self.name_ky:
            return self.name_ky
        return self.name_ru


class Curriculum(LocalizedNameMixin, TimeStampedModel):
    """A national school programme (first market: Kyrgyz Republic)."""

    code = models.SlugField(max_length=32, unique=True)
    country = models.CharField(max_length=2, default="KG")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "учебная программа"
        verbose_name_plural = "учебные программы"
        ordering = ("code",)


class Grade(LocalizedNameMixin, TimeStampedModel):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name="grades")
    number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(11)])

    class Meta:
        verbose_name = "класс"
        verbose_name_plural = "классы"
        ordering = ("curriculum", "number")
        constraints = [
            models.UniqueConstraint(fields=["curriculum", "number"], name="uniq_grade_per_curriculum")
        ]

    def __str__(self) -> str:
        return f"{self.number} класс"

    @property
    def stage(self) -> str:
        """Age band used to adapt explanations: primary (1–4), middle (5–8), senior (9–11)."""
        if self.number <= 4:
            return "primary"
        if self.number <= 8:
            return "middle"
        return "senior"


class Subject(LocalizedNameMixin, TimeStampedModel):
    class Strategy(models.TextChoices):
        MATH = "math", "Математика (формальная проверка)"
        NATIVE_LANGUAGE = "native_language", "Родной язык (правила, разбор)"
        FOREIGN_LANGUAGE = "foreign_language", "Иностранный язык"
        LITERATURE = "literature", "Литература"
        HUMANITIES = "humanities", "История / общество"
        SCIENCE = "science", "Естественные науки (физика, химия, биология, география)"
        INFORMATICS = "informatics", "Информатика"
        OTHER = "other", "Другое"

    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name="subjects")
    slug = models.SlugField(max_length=48)
    strategy = models.CharField(max_length=24, choices=Strategy.choices, default=Strategy.OTHER)
    icon = models.CharField(max_length=40, default="book-open", help_text="Имя иконки Lucide")
    color = models.CharField(max_length=16, default="lime", help_text="Ключ цвета из дизайн-системы")
    grade_from = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(11)]
    )
    grade_to = models.PositiveSmallIntegerField(
        default=11, validators=[MinValueValidator(1), MaxValueValidator(11)]
    )
    order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    ai_notes = models.TextField(
        blank=True, help_text="Подсказки для AI: терминология, особенности программы, типичные ошибки"
    )

    class Meta:
        verbose_name = "предмет"
        verbose_name_plural = "предметы"
        ordering = ("order", "name_ru")
        constraints = [
            models.UniqueConstraint(fields=["curriculum", "slug"], name="uniq_subject_slug_per_curriculum"),
            models.CheckConstraint(
                condition=models.Q(grade_from__lte=models.F("grade_to")), name="subject_grade_range"
            ),
        ]

    def available_for(self, grade_number: int) -> bool:
        return self.is_active and self.grade_from <= grade_number <= self.grade_to


class Section(LocalizedNameMixin, TimeStampedModel):
    """A chapter of a subject for one grade (e.g. «Дроби» for grade 5 maths)."""

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="sections")
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="sections")
    slug = models.SlugField(max_length=64)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "раздел"
        verbose_name_plural = "разделы"
        ordering = ("subject", "grade", "order")
        constraints = [models.UniqueConstraint(fields=["subject", "grade", "slug"], name="uniq_section_slug")]


class Topic(LocalizedNameMixin, TimeStampedModel):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="topics")
    slug = models.SlugField(max_length=64)
    description_ru = models.TextField(blank=True)
    description_ky = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    difficulty = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    keywords = models.JSONField(
        default=list, blank=True, help_text="Ключевые слова для сопоставления заданий"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "тема"
        verbose_name_plural = "темы"
        ordering = ("section", "order")
        constraints = [
            models.UniqueConstraint(fields=["section", "slug"], name="uniq_topic_slug_per_section")
        ]

    @property
    def subject(self) -> Subject:
        return self.section.subject

    @property
    def grade(self) -> Grade:
        return self.section.grade

    def description(self, lang: str = "ru") -> str:
        if lang == "ky" and self.description_ky:
            return self.description_ky
        return self.description_ru
