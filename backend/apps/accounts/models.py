from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel

from .constants import (
    AVATAR_CHOICES,
    FAMILY_CODE_ALPHABET,
    FAMILY_CODE_LENGTH,
    LANGUAGE_CHOICES,
)
from .managers import UserManager


def generate_family_code() -> str:
    return "".join(secrets.choice(FAMILY_CODE_ALPHABET) for _ in range(FAMILY_CODE_LENGTH))


class Family(UUIDModel, TimeStampedModel):
    """Tenant boundary: every parent, child and learning record belongs to exactly one family."""

    name = models.CharField(max_length=80, blank=True)
    code = models.CharField(max_length=FAMILY_CODE_LENGTH, unique=True, db_index=True)
    code_rotated_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "семья"
        verbose_name_plural = "семьи"

    def __str__(self) -> str:
        return self.name or f"Семья {self.code}"

    @classmethod
    def new_unique_code(cls) -> str:
        for _ in range(20):
            code = generate_family_code()
            if not cls.objects.filter(code=code).exists():
                return code
        raise RuntimeError("Could not allocate a unique family code")

    def rotate_code(self) -> str:
        self.code = type(self).new_unique_code()
        self.code_rotated_at = timezone.now()
        self.save(update_fields=["code", "code_rotated_at", "updated_at"])
        return self.code

    @property
    def display_code(self) -> str:
        return f"{self.code[:3]}-{self.code[3:]}"


class User(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "student", "Ученик"
        PARENT = "parent", "Родитель"
        ADMIN = "admin", "Администратор"
        TEACHER = "teacher", "Учитель"  # reserved for a future release

    email = models.EmailField("email", unique=True, null=True, blank=True)
    phone = models.CharField(max_length=32, unique=True, null=True, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, db_index=True)
    display_name = models.CharField(max_length=80)
    preferred_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    family = models.ForeignKey(
        Family, null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_role_display()})"

    def clean(self):
        super().clean()
        if self.email == "":
            self.email = None
        if self.phone == "":
            self.phone = None

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_parent(self) -> bool:
        return self.role == self.Role.PARENT

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser


class ParentProfile(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="parent_profile")
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="parents")
    country = models.CharField(max_length=2, default="KG")
    notify_weekly_report = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=True)

    class Meta:
        verbose_name = "профиль родителя"
        verbose_name_plural = "профили родителей"

    def __str__(self) -> str:
        return f"Родитель {self.user.display_name}"


class StudentProfile(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="students")
    nickname = models.CharField(max_length=40)
    grade = models.ForeignKey("curriculum.Grade", on_delete=models.PROTECT, related_name="students")
    curriculum = models.ForeignKey("curriculum.Curriculum", on_delete=models.PROTECT, related_name="students")
    instruction_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    explanation_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    avatar = models.CharField(max_length=32, choices=AVATAR_CHOICES, default="fox")
    pin_hash = models.CharField(max_length=128)
    pin_failed_attempts = models.PositiveSmallIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)
    pin_lockouts = models.PositiveSmallIntegerField(
        default=0, help_text="Сколько раз подряд срабатывала блокировка"
    )
    pin_requires_parent_reset = models.BooleanField(default=False)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    # Parental controls (enforced server-side, mirrored in the UI).
    share_conversations_with_parent = models.BooleanField(
        default=True, help_text="Родитель видит переписку с помощником, а не только итоги"
    )
    allow_photo_upload = models.BooleanField(default=True)
    allow_free_questions = models.BooleanField(default=True, help_text="Вопросы вне домашнего задания")
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    PIN_STATE_FIELDS = (
        "pin_failed_attempts",
        "pin_locked_until",
        "pin_lockouts",
        "pin_requires_parent_reset",
        "updated_at",
    )

    class Meta:
        verbose_name = "профиль ученика"
        verbose_name_plural = "профили учеников"
        indexes = [models.Index(fields=["family", "is_active"])]

    def __str__(self) -> str:
        return f"{self.nickname}, {self.grade.number} класс"

    # --- PIN handling -----------------------------------------------------
    def set_pin(self, raw_pin: str) -> None:
        self.pin_hash = make_password(raw_pin)
        self.pin_failed_attempts = 0
        self.pin_locked_until = None
        self.pin_lockouts = 0
        self.pin_requires_parent_reset = False

    def check_pin(self, raw_pin: str) -> bool:
        return check_password(raw_pin, self.pin_hash)

    @property
    def is_pin_locked(self) -> bool:
        if self.pin_requires_parent_reset:
            return True
        return bool(self.pin_locked_until and self.pin_locked_until > timezone.now())

    def register_pin_failure(self) -> bool:
        """Count a failed attempt. Returns True when this attempt triggered a lockout.

        Lockouts escalate: 15 min, 30 min, 60 min … and after ``CHILD_PIN_MAX_LOCKOUTS`` cycles
        the child can only be unlocked by a parent resetting the PIN. Callers must hold a row
        lock (``select_for_update``) so parallel attempts cannot skip the counter.
        """
        self.pin_failed_attempts += 1
        locked_now = False
        if self.pin_failed_attempts >= settings.CHILD_PIN_MAX_ATTEMPTS:
            self.pin_lockouts += 1
            self.pin_failed_attempts = 0
            locked_now = True
            if self.pin_lockouts >= settings.CHILD_PIN_MAX_LOCKOUTS:
                self.pin_requires_parent_reset = True
                self.pin_locked_until = None
            else:
                minutes = settings.CHILD_PIN_LOCK_MINUTES * (2 ** (self.pin_lockouts - 1))
                self.pin_locked_until = timezone.now() + timedelta(minutes=min(minutes, 24 * 60))
        self.save(update_fields=list(self.PIN_STATE_FIELDS))
        return locked_now

    def register_pin_success(self) -> None:
        if self.pin_failed_attempts or self.pin_locked_until or self.pin_lockouts:
            self.pin_failed_attempts = 0
            self.pin_locked_until = None
            self.pin_lockouts = 0
            self.save(update_fields=list(self.PIN_STATE_FIELDS))


class ParentStudentLink(UUIDModel, TimeStampedModel):
    class Relation(models.TextChoices):
        PARENT = "parent", "Родитель"
        GUARDIAN = "guardian", "Опекун"

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="child_links")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="parent_links")
    relation = models.CharField(max_length=16, choices=Relation.choices, default=Relation.PARENT)
    is_primary = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["parent", "student"], name="uniq_parent_student")]

    def __str__(self) -> str:
        return f"{self.parent} → {self.student}"


class ConsentRecord(UUIDModel):
    """Versioned, revocable consents. A revoked consent is never deleted — a new row is written."""

    class Type(models.TextChoices):
        TERMS = "terms", "Условия сервиса"
        PRIVACY = "privacy", "Политика конфиденциальности"
        CHILD_DATA = "child_data", "Обработка данных ребёнка"
        AI_PROCESSING = "ai_processing", "Обработка заданий AI-моделью"
        MARKETING = "marketing", "Маркетинговые сообщения"

    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="consents")
    student = models.ForeignKey(
        StudentProfile, null=True, blank=True, on_delete=models.CASCADE, related_name="consents"
    )
    consent_type = models.CharField(max_length=32, choices=Type.choices)
    version = models.CharField(max_length=32)
    granted = models.BooleanField(default=True)
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-granted_at",)
        indexes = [models.Index(fields=["granted_by", "consent_type", "granted"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(granted=True, revoked_at__isnull=True) | models.Q(granted=False),
                name="consent_revoked_only_when_not_granted",
            )
        ]

    def __str__(self) -> str:
        state = "✓" if self.granted else "✗"
        return f"{state} {self.get_consent_type_display()} v{self.version}"

    def revoke(self) -> None:
        self.granted = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["granted", "revoked_at"])
