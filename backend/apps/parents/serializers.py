from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import ParentProfile
from apps.accounts.serializers import StudentProfileSerializer
from apps.tutor.serializers import SessionSummarySerializer

from .models import ParentNotification


class DifficultTopicSerializer(serializers.Serializer):
    topic_id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.CharField()
    subject = serializers.DictField(allow_null=True)
    attempts_count = serializers.IntegerField(required=False)
    hints_count = serializers.IntegerField(required=False)
    last_activity_at = serializers.DateTimeField(required=False, allow_null=True)


class RecentQuizSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    topic_id = serializers.IntegerField(source="quiz.topic_id")
    topic_name = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    correct_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    score = serializers.SerializerMethodField()
    finished_at = serializers.DateTimeField()

    def _lang(self) -> str:
        return self.context.get("lang", "ru")

    def get_topic_name(self, obj) -> str:
        return obj.quiz.topic.name(self._lang())

    def get_subject(self, obj) -> dict:
        subject = obj.quiz.topic.section.subject
        return {
            "id": subject.id,
            "slug": subject.slug,
            "name": subject.name(self._lang()),
            "icon": subject.icon,
            "color": subject.color,
        }

    def get_score(self, obj) -> float:
        return round(obj.correct_count / obj.total_count, 3) if obj.total_count else 0.0


class ChildSummarySerializer(serializers.Serializer):
    sessions_total = serializers.IntegerField()
    completed_total = serializers.IntegerField()
    sessions_week = serializers.IntegerField()
    completed_week = serializers.IntegerField()
    independent_week = serializers.IntegerField()
    with_help_week = serializers.IntegerField()
    needs_review_week = serializers.IntegerField()
    independent_total = serializers.IntegerField()
    quizzes_week = serializers.IntegerField(default=0)
    last_activity_at = serializers.DateTimeField(allow_null=True)
    difficult_topics = DifficultTopicSerializer(many=True)


class ChildOverviewSerializer(serializers.Serializer):
    child = StudentProfileSerializer()
    summary = ChildSummarySerializer()


class OverviewSerializer(serializers.Serializer):
    children = ChildOverviewSerializer(many=True)
    unread_notifications = serializers.IntegerField()
    family_code = serializers.CharField()


class SubjectBreakdownSerializer(serializers.Serializer):
    subject = serializers.DictField()
    sessions = serializers.IntegerField()
    completed = serializers.IntegerField()
    independent = serializers.IntegerField()
    with_help = serializers.IntegerField()
    needs_review = serializers.IntegerField()
    hints_avg = serializers.FloatField()
    last_activity_at = serializers.DateTimeField(allow_null=True)
    topics = serializers.DictField(child=serializers.IntegerField())


class WeeklyReportSerializer(serializers.Serializer):
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    sessions = serializers.IntegerField()
    independent = serializers.IntegerField()
    with_help = serializers.IntegerField()
    needs_review = serializers.IntegerField()
    has_data = serializers.BooleanField()
    text = serializers.CharField()
    highlights = serializers.ListField(child=serializers.CharField())


class RecommendationSerializer(serializers.Serializer):
    kind = serializers.CharField()
    title = serializers.CharField()
    text = serializers.CharField()
    action = serializers.DictField(allow_null=True)


class ChildProgressSerializer(serializers.Serializer):
    child = StudentProfileSerializer()
    summary = ChildSummarySerializer()
    subjects = SubjectBreakdownSerializer(many=True)
    difficult_topics = DifficultTopicSerializer(many=True)
    weekly_report = WeeklyReportSerializer()
    recommendations = RecommendationSerializer(many=True)
    recent_sessions = SessionSummarySerializer(many=True)
    recent_quizzes = RecentQuizSerializer(many=True)


class NotificationSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    student_id = serializers.UUIDField(read_only=True)
    student_nickname = serializers.CharField(source="student.nickname", read_only=True, default=None)

    class Meta:
        model = ParentNotification
        fields = (
            "id",
            "kind",
            "kind_label",
            "title",
            "body",
            "data",
            "student_id",
            "student_nickname",
            "read_at",
            "created_at",
        )
        read_only_fields = fields


class FamilySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentProfile
        fields = ("notify_weekly_report", "notify_email", "country")
        read_only_fields = ("country",)


class FamilyDeleteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm = serializers.BooleanField()

    def validate_confirm(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("Подтвердите удаление.")
        return value
