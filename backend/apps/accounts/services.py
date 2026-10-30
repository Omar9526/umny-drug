"""Account use-cases. Views stay thin; every multi-step write happens here inside a transaction."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.audit import audit, client_ip
from apps.core.exceptions import DomainError

from .models import ConsentRecord, Family, ParentProfile, ParentStudentLink, StudentProfile, User

logger = logging.getLogger("umnydrug.accounts")

REQUIRED_PARENT_CONSENTS = (ConsentRecord.Type.TERMS, ConsentRecord.Type.PRIVACY)
CHILD_CONSENTS = (ConsentRecord.Type.CHILD_DATA, ConsentRecord.Type.AI_PROCESSING)


class InvalidCredentials(DomainError):
    status_code = 401
    default_code = "invalid_credentials"
    default_detail = "Неверный код семьи или PIN."


class AccountLocked(DomainError):
    status_code = 423
    default_code = "account_locked"
    default_detail = "Слишком много неверных попыток. Попробуй через несколько минут."


class PinResetRequired(DomainError):
    status_code = 423
    default_code = "pin_reset_required"
    default_detail = "Вход заблокирован. Попроси родителей сменить PIN в их кабинете."


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def issue_tokens(user: User) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    return str(refresh.access_token), str(refresh)


def revoke_user_sessions(*users: User) -> int:
    """Blacklist every outstanding refresh token of the given users (access tokens expire in minutes).

    A device whose session is revoked (stolen refresh token, deleted family) loses its push subscription as
    well, otherwise it would keep receiving the children's notifications.
    """
    from apps.parents.models import PushSubscription  # parents depends on accounts; keep the import lazy

    PushSubscription.objects.filter(parent__user__in=users).delete()
    revoked = 0
    for token in OutstandingToken.objects.filter(user__in=users):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        revoked += int(created)
    return revoked


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
        path=settings.AUTH_COOKIE_PATH,
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.AUTH_COOKIE_NAME,
        domain=settings.AUTH_COOKIE_DOMAIN,
        path=settings.AUTH_COOKIE_PATH,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


# ---------------------------------------------------------------------------
# Parent registration
# ---------------------------------------------------------------------------
@transaction.atomic
def register_parent(
    *,
    display_name: str,
    email: str,
    password: str,
    preferred_language: str,
    consents: dict[str, bool],
    request=None,
) -> User:
    # The serializer already enforces this; kept as a server-side invariant for other callers.
    missing = [c for c in REQUIRED_PARENT_CONSENTS if not consents.get(c)]
    if missing:
        raise DomainError(
            "Нужно принять условия сервиса и политику конфиденциальности.",
            code="consent_required",
            status_code=400,
        )

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                role=User.Role.PARENT,
                display_name=display_name.strip(),
                preferred_language=preferred_language,
            )
    except IntegrityError:
        raise serializers.ValidationError(
            {"email": ["Аккаунт с таким email уже существует. Попробуйте войти."]}
        )
    family = Family.objects.create(
        code=Family.new_unique_code(), created_by=user, name=f"Семья {user.display_name}"
    )
    user.family = family
    user.save(update_fields=["family", "updated_at"])
    ParentProfile.objects.create(user=user, family=family)

    ip = client_ip(request)
    for consent_type in (ConsentRecord.Type.TERMS, ConsentRecord.Type.PRIVACY, ConsentRecord.Type.MARKETING):
        if consents.get(consent_type):
            ConsentRecord.objects.create(
                granted_by=user,
                consent_type=consent_type,
                version=settings.CONSENT_TERMS_VERSION,
                ip_address=ip,
            )
    audit("parent.registered", actor=user, target=family, request=request)
    return user


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------
@transaction.atomic
def create_child(
    *,
    parent: ParentProfile,
    nickname: str,
    grade,
    language: str,
    avatar: str,
    pin: str,
    consent_confirmed: bool,
    request=None,
) -> StudentProfile:
    if not consent_confirmed:
        raise DomainError(
            "Подтвердите, что вы законный представитель ребёнка и согласны на обработку его учебных данных.",
            code="consent_required",
            status_code=400,
        )
    family = parent.family
    user = User.objects.create_user(
        email=None,
        password=None,
        role=User.Role.STUDENT,
        display_name=nickname.strip(),
        preferred_language=language,
        family=family,
    )
    student = StudentProfile(
        user=user,
        family=family,
        nickname=nickname.strip(),
        grade=grade,
        curriculum=grade.curriculum,
        language=language,
        avatar=avatar,
    )
    student.set_pin(pin)
    student.save()
    ParentStudentLink.objects.create(parent=parent, student=student, is_primary=True)

    ip = client_ip(request)
    for consent_type in CHILD_CONSENTS:
        ConsentRecord.objects.create(
            granted_by=parent.user,
            student=student,
            consent_type=consent_type,
            version=settings.CONSENT_TERMS_VERSION,
            ip_address=ip,
        )
    audit("child.created", actor=parent.user, target=student, request=request, grade=grade.number)
    return student


@transaction.atomic
def update_child(
    *, parent: ParentProfile, student: StudentProfile, data: dict, request=None
) -> StudentProfile:
    """Apply validated profile fields and keep the linked user row consistent."""
    for field, value in data.items():
        setattr(student, field, value)
    student.save()
    user_fields: list[str] = []
    if "nickname" in data:
        student.user.display_name = student.nickname
        user_fields.append("display_name")
    if "language" in data:
        student.user.preferred_language = student.language
        user_fields.append("preferred_language")
    if user_fields:
        student.user.save(update_fields=[*user_fields, "updated_at"])
    audit("child.updated", actor=parent.user, target=student, request=request, fields=sorted(data))
    return student


@transaction.atomic
def reset_child_pin(*, parent: ParentProfile, student: StudentProfile, pin: str, request=None) -> None:
    student.set_pin(pin)
    student.save(update_fields=["pin_hash", *StudentProfile.PIN_STATE_FIELDS])
    revoked = revoke_user_sessions(student.user)
    audit("child.pin_reset", actor=parent.user, target=student, request=request, sessions_revoked=revoked)


@transaction.atomic
def deactivate_child(*, parent: ParentProfile, student: StudentProfile, request=None) -> None:
    now = timezone.now()
    student.is_active = False
    student.deleted_at = now
    student.save(update_fields=["is_active", "deleted_at", "updated_at"])
    student.user.is_active = False
    student.user.save(update_fields=["is_active", "updated_at"])
    for consent in student.consents.filter(granted=True):
        consent.revoke()
    revoke_user_sessions(student.user)
    audit("child.deactivated", actor=parent.user, target=student, request=request)


@transaction.atomic
def rotate_family_code(*, parent: ParentProfile, request=None) -> str:
    code = parent.family.rotate_code()
    students = list(User.objects.filter(student_profile__family=parent.family))
    revoked = revoke_user_sessions(*students) if students else 0
    audit(
        "family.code_rotated",
        actor=parent.user,
        target=parent.family,
        request=request,
        sessions_revoked=revoked,
    )
    return code


# ---------------------------------------------------------------------------
# Child login
# ---------------------------------------------------------------------------
def normalize_family_code(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def lookup_family(family_code: str) -> Family:
    code = normalize_family_code(family_code)
    try:
        return Family.objects.get(code=code)
    except Family.DoesNotExist:
        raise InvalidCredentials("Такой код семьи не найден. Проверь код у родителей.")


def _notify_parents_about_lockout(student: StudentProfile, permanent: bool) -> None:
    from apps.parents.models import ParentNotification
    from apps.parents.services import create_notification

    title = "Вход ребёнка заблокирован" if permanent else "Несколько неверных PIN подряд"
    body = (
        f"{student.nickname}: вход заблокирован до смены PIN. Смените PIN в кабинете, если это не ребёнок."
        if permanent
        else f"{student.nickname}: вход временно приостановлен после неверных PIN."
    )
    for parent in student.family.parents.all():
        create_notification(
            parent=parent,
            student=student,
            kind=ParentNotification.Kind.SYSTEM,
            title=title,
            body=body,
            data={"permanent": permanent},
        )


def authenticate_child(*, family_code: str, student_id, pin: str, request=None) -> StudentProfile:
    """Verify family code + PIN under a row lock.

    Failure bookkeeping (attempt counter, lockout, audit, parent notification) is committed
    *before* the error is raised, so a rejected attempt is never rolled back.
    """
    family = lookup_family(family_code)
    error: DomainError | None = None
    with transaction.atomic():
        try:
            student = (
                StudentProfile.objects.select_for_update()
                .select_related("user", "grade")
                .get(id=student_id, family=family, is_active=True, user__is_active=True)
            )
        except (StudentProfile.DoesNotExist, ValueError):
            raise InvalidCredentials()

        if student.pin_requires_parent_reset:
            audit("child.login_locked", target=student, request=request, permanent=True)
            error = PinResetRequired()
        elif student.is_pin_locked:
            audit("child.login_locked", target=student, request=request)
            error = AccountLocked()
        elif not student.check_pin(pin):
            locked_now = student.register_pin_failure()
            audit("child.login_failed", target=student, request=request)
            if locked_now:
                _notify_parents_about_lockout(student, permanent=student.pin_requires_parent_reset)
                error = PinResetRequired() if student.pin_requires_parent_reset else AccountLocked()
            else:
                error = InvalidCredentials()
        else:
            student.register_pin_success()

    if error is not None:
        raise error
    audit("child.login", actor=student.user, target=student, request=request)
    return student
