from __future__ import annotations

from rest_framework import serializers

from ai.registry import provider_status
from apps.curriculum.serializers import SubjectSerializer
from apps.learning.models import AnswerAttempt, VerificationResult

from .models import AIMessage, LearningSession, SolutionStep


class SessionSummarySerializer(serializers.ModelSerializer):
    """Compact card used on the dashboard, in history and in the parent cabinet."""

    subject = SubjectSerializer(read_only=True)
    topic_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    outcome_label = serializers.CharField(source="get_outcome_display", read_only=True)
    mode_label = serializers.CharField(source="get_mode_display", read_only=True)
    assignment_id = serializers.UUIDField(read_only=True)
    assignment_text = serializers.SerializerMethodField()
    topic_id = serializers.IntegerField(read_only=True)
    is_independent = serializers.BooleanField(read_only=True)

    class Meta:
        model = LearningSession
        fields = (
            "id",
            "title",
            "mode",
            "mode_label",
            "status",
            "status_label",
            "outcome",
            "outcome_label",
            "subject",
            "topic_name",
            "topic_id",
            "assignment_id",
            "assignment_text",
            "hints_used",
            "attempts_count",
            "correct_attempts",
            "is_independent",
            "created_at",
            "last_activity_at",
            "ended_at",
        )
        read_only_fields = fields

    def get_topic_name(self, obj: LearningSession) -> str | None:
        if obj.topic_id is None:
            return None
        return obj.topic.name(self.context.get("lang", "ru"))

    def get_assignment_text(self, obj: LearningSession) -> str | None:
        if obj.assignment_id is None:
            return None
        text = obj.assignment.text
        return text if len(text) <= 160 else text[:157] + "…"


class SessionStateSerializer(serializers.ModelSerializer):
    """Mutable counters the chat UI needs after every turn."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    outcome_label = serializers.CharField(source="get_outcome_display", read_only=True)

    class Meta:
        model = LearningSession
        fields = (
            "id",
            "status",
            "status_label",
            "outcome",
            "outcome_label",
            "hints_used",
            "explanations_count",
            "attempts_count",
            "correct_attempts",
            "solution_revealed",
            "understood_points",
            "mistakes_fixed",
            "ended_at",
            "last_activity_at",
        )
        read_only_fields = fields


# Server-only parts of a tutor turn: the child must never see the expected answer or the rubric.
CLIENT_HIDDEN_PAYLOAD_KEYS = frozenset({"expected_answer", "rubric"})


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ("id", "role", "command", "content", "payload", "flagged", "created_at")
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        payload = data.get("payload") or {}
        data["payload"] = {k: v for k, v in payload.items() if k not in CLIENT_HIDDEN_PAYLOAD_KEYS}
        return data


class SolutionStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolutionStep
        fields = ("id", "order", "title", "content", "is_hint", "revealed_at")
        read_only_fields = fields


class VerificationSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    verdict_label = serializers.CharField(source="get_verdict_display", read_only=True)

    class Meta:
        model = VerificationResult
        fields = ("method", "method_label", "verdict", "verdict_label", "confidence", "feedback")
        read_only_fields = fields


class AnswerAttemptSerializer(serializers.ModelSerializer):
    verification = VerificationSerializer(read_only=True)

    class Meta:
        model = AnswerAttempt
        fields = (
            "id",
            "attempt_number",
            "answer_text",
            "hints_before",
            "is_independent",
            "verification",
            "created_at",
        )
        read_only_fields = fields


class SessionDetailSerializer(SessionSummarySerializer):
    messages = serializers.SerializerMethodField()
    steps = SolutionStepSerializer(many=True, read_only=True)
    attempts = AnswerAttemptSerializer(many=True, read_only=True)
    assignment = serializers.SerializerMethodField()
    siblings = serializers.SerializerMethodField()
    suggested_commands = serializers.SerializerMethodField()
    check_question = serializers.SerializerMethodField()
    answer_kind = serializers.SerializerMethodField()
    demo_mode = serializers.SerializerMethodField()
    state = SessionStateSerializer(source="*", read_only=True)
    language = serializers.CharField(read_only=True)

    class Meta(SessionSummarySerializer.Meta):
        fields = (
            *SessionSummarySerializer.Meta.fields,
            "language",
            "state",
            "messages",
            "steps",
            "attempts",
            "assignment",
            "siblings",
            "suggested_commands",
            "check_question",
            "answer_kind",
            "demo_mode",
        )
        read_only_fields = fields

    def get_messages(self, obj: LearningSession):
        conversation = getattr(obj, "conversation", None)
        if conversation is None:
            return []
        prefetched = getattr(conversation, "_prefetched_objects_cache", {}).get("messages")
        messages = (
            prefetched
            if prefetched is not None
            else conversation.messages.exclude(role=AIMessage.Role.SYSTEM)
        )
        return AIMessageSerializer(messages, many=True).data

    def get_assignment(self, obj: LearningSession):
        if obj.assignment_id is None:
            return None
        from apps.assignments.serializers import AssignmentImageSerializer

        assignment = obj.assignment
        images = assignment.upload.images.all() if assignment.upload_id else []
        return {
            "id": str(assignment.id),
            "label": assignment.label,
            "text": assignment.text,
            "status": assignment.status,
            "images": AssignmentImageSerializer(images, many=True).data,
            "upload_id": str(assignment.upload_id) if assignment.upload_id else None,
        }

    def get_siblings(self, obj: LearningSession):
        if obj.assignment_id is None or obj.assignment.upload_id is None:
            return []
        from apps.assignments.serializers import TaskBriefSerializer, _sessions_prefetch

        siblings = (
            obj.assignment.upload.assignments.exclude(id=obj.assignment_id)
            .select_related("subject", "topic__section")
            .prefetch_related(_sessions_prefetch())
        )
        return TaskBriefSerializer(siblings, many=True, context=self.context).data

    def _last_payload(self, obj: LearningSession) -> dict:
        cache = getattr(self, "_payload_cache", None)
        if cache is None:
            cache = self._payload_cache = {}
        if obj.pk in cache:
            return cache[obj.pk]
        conversation = getattr(obj, "conversation", None)
        payload: dict = {}
        if conversation is not None:
            prefetched = getattr(conversation, "_prefetched_objects_cache", {}).get("messages")
            if prefetched is not None:
                for message in reversed(list(prefetched)):
                    if message.role == AIMessage.Role.ASSISTANT and message.command != "check":
                        payload = message.payload or {}
                        break
            else:
                message = (
                    conversation.messages.filter(role=AIMessage.Role.ASSISTANT)
                    .exclude(command="check")
                    .order_by("-created_at")
                    .first()
                )
                payload = (message.payload or {}) if message else {}
        cache[obj.pk] = payload
        return payload

    def get_suggested_commands(self, obj: LearningSession):
        return self._last_payload(obj).get("suggested_commands", [])

    def get_check_question(self, obj: LearningSession):
        return self._last_payload(obj).get("check_question", "")

    def get_answer_kind(self, obj: LearningSession):
        return self._last_payload(obj).get("answer_kind", "none")

    def get_demo_mode(self, obj: LearningSession) -> bool:
        conversation = getattr(obj, "conversation", None)
        return conversation.demo_mode if conversation else provider_status()["demo_mode"]


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class CreateSessionSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=LearningSession.Mode.choices)
    subject_slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)
    topic_id = serializers.IntegerField(required=False, allow_null=True)
    question = serializers.CharField(required=False, allow_blank=True, max_length=2000, trim_whitespace=True)

    def validate_mode(self, value):
        if value == LearningSession.Mode.HOMEWORK:
            raise serializers.ValidationError(
                "Разбор домашнего задания начинается через подтверждение задания."
            )
        return value


class TurnSerializer(serializers.Serializer):
    command = serializers.CharField(required=False, allow_blank=True, max_length=24, default="")
    content = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class CheckAnswerSerializer(serializers.Serializer):
    answer_text = serializers.CharField(max_length=2000, trim_whitespace=True)


class FlagSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
