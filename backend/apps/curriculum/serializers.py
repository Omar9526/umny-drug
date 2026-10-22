from __future__ import annotations

from rest_framework import serializers

from .models import Curriculum, Grade, Section, Subject, Topic


class LocalizedSerializerMixin:
    """Adds a ``name`` field resolved for ``context["lang"]`` (defaults to ru)."""

    def _lang(self) -> str:
        return self.context.get("lang", "ru") if hasattr(self, "context") else "ru"

    def get_name(self, obj) -> str:
        return obj.name(self._lang())


class GradeSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    stage = serializers.CharField(read_only=True)

    class Meta:
        model = Grade
        fields = ("id", "number", "name", "stage")
        read_only_fields = fields


class CurriculumBriefSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Curriculum
        fields = ("id", "code", "name", "country")
        read_only_fields = fields


class CurriculumSerializer(CurriculumBriefSerializer):
    grades = GradeSerializer(many=True, read_only=True)

    class Meta(CurriculumBriefSerializer.Meta):
        fields = (*CurriculumBriefSerializer.Meta.fields, "grades")
        read_only_fields = fields


class SubjectSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    topics_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Subject
        fields = ("id", "slug", "name", "icon", "color", "strategy", "grade_from", "grade_to", "topics_count")
        read_only_fields = fields


class TopicSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    progress_status = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = ("id", "slug", "name", "description", "order", "difficulty", "progress_status")
        read_only_fields = fields

    def get_description(self, obj: Topic) -> str:
        return obj.description(self._lang())

    def get_progress_status(self, obj: Topic) -> str:
        progress = self.context.get("progress_by_topic") or {}
        return progress.get(obj.id, "not_started")


class SectionSerializer(LocalizedSerializerMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ("id", "slug", "name", "order", "topics")
        read_only_fields = fields

    def get_topics(self, obj: Section):
        topics = [t for t in obj.topics.all() if t.is_active]
        return TopicSerializer(topics, many=True, context=self.context).data


class SubjectDetailSerializer(SubjectSerializer):
    sections = serializers.SerializerMethodField()
    grade = GradeSerializer(read_only=True)

    class Meta(SubjectSerializer.Meta):
        fields = (*SubjectSerializer.Meta.fields, "grade", "sections")
        read_only_fields = fields

    def get_sections(self, obj: Subject):
        sections = self.context.get("sections", [])
        return SectionSerializer(sections, many=True, context=self.context).data
