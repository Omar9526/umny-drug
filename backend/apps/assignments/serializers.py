from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import serializers

from apps.accounts.constants import LANGUAGE_CHOICES
from apps.curriculum.models import Subject, Topic
from apps.curriculum.serializers import GradeSerializer, SubjectSerializer

from .models import Assignment, AssignmentImage, AssignmentUpload


def _lang(ctx) -> str:
    return ctx.get("lang", "ru") if ctx else "ru"


def _sessions_prefetch() -> Prefetch:
    from apps.tutor.models import LearningSession

    return Prefetch(
        "sessions", queryset=LearningSession.objects.order_by("-created_at"), to_attr="_prefetched_sessions"
    )


class UploadCreateSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=AssignmentUpload.Source.choices)
    typed_text = serializers.CharField(
        required=False, allow_blank=True, max_length=6000, trim_whitespace=True
    )
    language_hint = serializers.ChoiceField(choices=LANGUAGE_CHOICES, required=False)


class AssignmentImageSerializer(serializers.ModelSerializer):
    available = serializers.BooleanField(source="is_available", read_only=True)

    class Meta:
        model = AssignmentImage
        fields = ("id", "order", "width", "height", "available")
        read_only_fields = fields


class TopicBriefSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = ("id", "slug", "name")
        read_only_fields = fields

    def get_name(self, obj: Topic) -> str:
        return obj.name(_lang(self.context))


class TaskBriefSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    topic = TopicBriefSerializer(read_only=True)
    text = serializers.CharField(read_only=True)
    excerpt = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    session_id = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = (
            "id",
            "index_in_upload",
            "label",
            "text",
            "excerpt",
            "subject",
            "topic",
            "status",
            "status_label",
            "session_id",
        )
        read_only_fields = fields

    def get_excerpt(self, obj: Assignment) -> str:
        text = obj.text
        return text if len(text) <= 140 else text[:137] + "…"

    def get_session_id(self, obj: Assignment):
        sessions = getattr(obj, "_prefetched_sessions", None)
        if sessions is None:
            session = obj.sessions.order_by("-created_at").first()
            return str(session.id) if session else None
        return str(sessions[0].id) if sessions else None


class UploadSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    images = AssignmentImageSerializer(many=True, read_only=True)
    tasks = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentUpload
        fields = (
            "id",
            "status",
            "status_label",
            "source",
            "typed_text",
            "error_code",
            "error_message",
            "demo_mode",
            "images",
            "tasks",
            "created_at",
            "processed_at",
        )
        read_only_fields = fields

    def get_tasks(self, obj: AssignmentUpload):
        tasks = (
            obj.assignments.select_related("subject", "topic__section")
            .prefetch_related(_sessions_prefetch())
            .order_by("index_in_upload")
        )
        return TaskBriefSerializer(tasks, many=True, context=self.context).data


class AssignmentDetailSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    topic = TopicBriefSerializer(read_only=True)
    grade = GradeSerializer(read_only=True)
    text = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    images = serializers.SerializerMethodField()
    siblings = serializers.SerializerMethodField()
    session_id = serializers.SerializerMethodField()
    upload_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Assignment
        fields = (
            "id",
            "label",
            "recognized_text",
            "confirmed_text",
            "text",
            "text_edited",
            "status",
            "status_label",
            "subject",
            "topic",
            "grade",
            "detection",
            "language",
            "upload_id",
            "images",
            "siblings",
            "session_id",
            "created_at",
            "confirmed_at",
            "completed_at",
        )
        read_only_fields = fields

    def get_images(self, obj: Assignment):
        if obj.upload_id is None:
            return []
        return AssignmentImageSerializer(obj.upload.images.all(), many=True).data

    def get_siblings(self, obj: Assignment):
        if obj.upload_id is None:
            return []
        siblings = (
            obj.upload.assignments.exclude(id=obj.id)
            .select_related("subject", "topic__section")
            .prefetch_related(_sessions_prefetch())
        )
        return TaskBriefSerializer(siblings, many=True, context=self.context).data

    def get_session_id(self, obj: Assignment):
        session = obj.sessions.order_by("-created_at").first()
        return str(session.id) if session else None


class ConfirmSerializer(serializers.Serializer):
    confirmed_text = serializers.CharField(min_length=1, max_length=6000, trim_whitespace=True)
    subject_slug = serializers.SlugField(required=False, allow_null=True, allow_blank=True)
    topic_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        student = self.context["student"]
        slug = attrs.get("subject_slug")
        attrs["subject_provided"] = "subject_slug" in self.initial_data
        attrs["subject"] = None
        if slug:
            subject = Subject.objects.filter(curriculum=student.curriculum, slug=slug, is_active=True).first()
            if subject is None or not subject.available_for(student.grade.number):
                raise serializers.ValidationError({"subject_slug": ["Такого предмета нет в твоём классе."]})
            attrs["subject"] = subject
        topic_id = attrs.get("topic_id")
        attrs["topic"] = None
        if topic_id:
            topic = (
                Topic.objects.filter(id=topic_id, section__grade=student.grade, is_active=True)
                .select_related("section__subject")
                .first()
            )
            if topic is None:
                raise serializers.ValidationError({"topic_id": ["Тема не найдена."]})
            attrs["topic"] = topic
        return attrs
