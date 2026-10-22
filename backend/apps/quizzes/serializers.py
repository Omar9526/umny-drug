from __future__ import annotations

from rest_framework import serializers

from apps.learning.models import LearningProgress

from .models import Question, Quiz, QuizAttempt


class QuestionPublicSerializer(serializers.ModelSerializer):
    """What the child sees before answering: never the correct answer."""

    prompt = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    hint = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ("id", "order", "type", "prompt", "options", "hint")
        read_only_fields = fields

    def _lang(self) -> str:
        return self.context.get("lang", "ru")

    def get_prompt(self, obj: Question) -> str:
        return obj.prompt(self._lang())

    def get_options(self, obj: Question) -> list[dict]:
        return obj.option_texts(self._lang())

    def get_hint(self, obj: Question) -> str:
        return obj.hint(self._lang())


class QuizBriefSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ("id", "title", "source", "language")
        read_only_fields = fields

    def get_title(self, obj: Quiz) -> str:
        return obj.name(self.context.get("lang", "ru"))


class QuizAttemptSerializer(serializers.ModelSerializer):
    quiz = QuizBriefSerializer(read_only=True)
    topic = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    progress_status = serializers.SerializerMethodField()

    class Meta:
        model = QuizAttempt
        fields = (
            "id",
            "status",
            "mode",
            "quiz",
            "topic",
            "questions",
            "answers",
            "results",
            "correct_count",
            "total_count",
            "score",
            "topics_to_review",
            "progress_status",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields

    def _lang(self) -> str:
        return self.context.get("lang", "ru")

    def get_topic(self, obj: QuizAttempt) -> dict:
        topic = obj.quiz.topic
        subject = topic.section.subject
        lang = self._lang()
        return {
            "id": topic.id,
            "name": topic.name(lang),
            "subject": {
                "id": subject.id,
                "slug": subject.slug,
                "name": subject.name(lang),
                "icon": subject.icon,
                "color": subject.color,
            },
        }

    def get_questions(self, obj: QuizAttempt) -> list[dict]:
        questions = obj.quiz.questions.all().order_by("order")
        return QuestionPublicSerializer(questions, many=True, context=self.context).data

    def get_score(self, obj: QuizAttempt) -> float:
        return round(obj.correct_count / obj.total_count, 3) if obj.total_count else 0.0

    def get_progress_status(self, obj: QuizAttempt) -> str:
        if obj.status != QuizAttempt.Status.FINISHED:
            return ""
        progress = LearningProgress.objects.filter(student=obj.student, topic_id=obj.quiz.topic_id).first()
        return progress.status if progress else "not_started"


class StartQuizSerializer(serializers.Serializer):
    topic_id = serializers.IntegerField(min_value=1)


class AnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    answer = serializers.JSONField()

    def validate_answer(self, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise serializers.ValidationError("Введите ответ.")
            if len(value) > 200:
                raise serializers.ValidationError("Слишком длинный ответ.")
            return value
        if (
            isinstance(value, list)
            and 0 < len(value) <= 8
            and all(isinstance(v, str) and len(v) <= 100 for v in value)
        ):
            return value
        raise serializers.ValidationError("Ответ должен быть строкой или списком строк.")
