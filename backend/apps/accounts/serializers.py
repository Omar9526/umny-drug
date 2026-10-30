from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.curriculum.models import Grade
from apps.curriculum.serializers import CurriculumBriefSerializer, GradeSerializer

from .constants import AVATAR_KEYS, LANGUAGE_CHOICES, PIN_MAX_LENGTH, PIN_MIN_LENGTH
from .models import ConsentRecord, Family, ParentProfile, StudentProfile, User


def validate_pin_value(value: str) -> str:
    value = value.strip()
    if not value.isdigit() or not (PIN_MIN_LENGTH <= len(value) <= PIN_MAX_LENGTH):
        raise serializers.ValidationError(f"PIN — от {PIN_MIN_LENGTH} до {PIN_MAX_LENGTH} цифр.")
    if len(set(value)) == 1:
        raise serializers.ValidationError("PIN не должен состоять из одинаковых цифр.")
    return value


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class FamilySerializer(serializers.ModelSerializer):
    display_code = serializers.CharField(read_only=True)

    class Meta:
        model = Family
        fields = ("id", "name", "code", "display_code", "code_rotated_at")
        read_only_fields = fields


class StudentProfileSerializer(serializers.ModelSerializer):
    grade = GradeSerializer(read_only=True)
    curriculum = CurriculumBriefSerializer(read_only=True)
    onboarding_completed = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = (
            "id",
            "nickname",
            "avatar",
            "grade",
            "curriculum",
            "language",
            "onboarding_completed",
            "share_conversations_with_parent",
            "allow_photo_upload",
            "allow_free_questions",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    def get_onboarding_completed(self, obj: StudentProfile) -> bool:
        return obj.onboarding_completed_at is not None


class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    grade_id = serializers.PrimaryKeyRelatedField(
        source="grade", queryset=Grade.objects.all(), required=False
    )
    onboarding_completed = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = StudentProfile
        fields = (
            "avatar",
            "language",
            "grade_id",
            "onboarding_completed",
        )

    def validate_avatar(self, value: str) -> str:
        if value not in AVATAR_KEYS:
            raise serializers.ValidationError("Неизвестный аватар.")
        return value

    def validate_grade_id(self, grade: Grade) -> Grade:
        if grade.curriculum_id != self.instance.curriculum_id:
            raise serializers.ValidationError("Класс не относится к учебной программе ученика.")
        return grade

    def update(self, instance: StudentProfile, validated_data):
        completed = validated_data.pop("onboarding_completed", None)
        if completed and instance.onboarding_completed_at is None:
            instance.onboarding_completed_at = timezone.now()
        instance = super().update(instance, validated_data)
        if "language" in validated_data:
            instance.user.preferred_language = validated_data["language"]
            instance.user.save(update_fields=["preferred_language", "updated_at"])
        return instance


class ParentProfileSerializer(serializers.ModelSerializer):
    family = FamilySerializer(read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = ParentProfile
        fields = ("id", "family", "country", "notify_weekly_report", "notify_email", "children_count")
        read_only_fields = ("id", "family", "children_count")

    def get_children_count(self, obj: ParentProfile) -> int:
        return obj.family.students.filter(is_active=True).count()


class UserSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "role", "display_name", "email", "preferred_language", "student", "parent")
        read_only_fields = fields

    def to_representation(self, instance: User):
        data = super().to_representation(instance)
        if not instance.is_parent and not instance.is_admin_role:
            data.pop("email", None)
        return data

    def get_student(self, obj: User):
        profile = getattr(obj, "student_profile", None)
        return StudentProfileSerializer(profile).data if profile else None

    def get_parent(self, obj: User):
        profile = getattr(obj, "parent_profile", None)
        return ParentProfileSerializer(profile).data if profile else None


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = UserSerializer()


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class ParentConsentsSerializer(serializers.Serializer):
    terms = serializers.BooleanField()
    privacy = serializers.BooleanField()
    marketing = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("terms") or not attrs.get("privacy"):
            raise serializers.ValidationError("Нужно принять условия сервиса и политику конфиденциальности.")
        return attrs


class ParentRegisterSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=80, min_length=2)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    preferred_language = serializers.ChoiceField(choices=LANGUAGE_CHOICES, default="ru")
    consents = ParentConsentsSerializer()

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Аккаунт с таким email уже существует. Попробуйте войти.")
        return value

    def validate(self, attrs):
        probe = User(email=attrs["email"], display_name=attrs["display_name"], role=User.Role.PARENT)
        try:
            validate_password(attrs["password"], user=probe)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"].lower().strip(),
            password=attrs["password"],
        )
        if user is None or not user.is_active or user.is_student:
            raise serializers.ValidationError({"non_field_errors": ["Неверный email или пароль."]})
        attrs["user"] = user
        return attrs


class ChildLookupSerializer(serializers.Serializer):
    family_code = serializers.CharField(min_length=6, max_length=12)


class ChildLoginSerializer(serializers.Serializer):
    family_code = serializers.CharField(min_length=6, max_length=12)
    student_id = serializers.UUIDField()
    pin = serializers.CharField(min_length=PIN_MIN_LENGTH, max_length=PIN_MAX_LENGTH)


class ChildPublicSerializer(serializers.ModelSerializer):
    """What a device that knows only the family code may see: no surnames, no progress."""

    grade_number = serializers.IntegerField(source="grade.number", read_only=True)

    class Meta:
        model = StudentProfile
        fields = ("id", "nickname", "avatar", "grade_number")
        read_only_fields = fields


class ChildCreateSerializer(serializers.Serializer):
    nickname = serializers.CharField(min_length=2, max_length=40)
    grade_id = serializers.PrimaryKeyRelatedField(queryset=Grade.objects.select_related("curriculum"))
    language = serializers.ChoiceField(choices=LANGUAGE_CHOICES, default="ru")
    avatar = serializers.ChoiceField(choices=AVATAR_KEYS, default="fox")
    pin = serializers.CharField(write_only=True)
    consent_confirmed = serializers.BooleanField()

    def validate_pin(self, value: str) -> str:
        return validate_pin_value(value)


class ChildUpdateSerializer(serializers.ModelSerializer):
    grade_id = serializers.PrimaryKeyRelatedField(
        source="grade", queryset=Grade.objects.all(), required=False
    )

    class Meta:
        model = StudentProfile
        fields = (
            "nickname",
            "avatar",
            "language",
            "grade_id",
            "share_conversations_with_parent",
            "allow_photo_upload",
            "allow_free_questions",
        )
        extra_kwargs = {"nickname": {"min_length": 2}}

    def validate_grade_id(self, grade: Grade) -> Grade:
        if grade.curriculum_id != self.instance.curriculum_id:
            raise serializers.ValidationError("Класс не относится к учебной программе ученика.")
        return grade


class ChildPinSerializer(serializers.Serializer):
    pin = serializers.CharField(write_only=True)

    def validate_pin(self, value: str) -> str:
        return validate_pin_value(value)


class ConsentRecordSerializer(serializers.ModelSerializer):
    consent_type_label = serializers.CharField(source="get_consent_type_display", read_only=True)
    student_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ConsentRecord
        fields = (
            "id",
            "consent_type",
            "consent_type_label",
            "version",
            "granted",
            "granted_at",
            "revoked_at",
            "student_id",
        )
        read_only_fields = fields
