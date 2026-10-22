from __future__ import annotations

from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import DomainError
from apps.core.scope import request_lang as _lang
from apps.core.scope import student_in_scope as _student_in_scope
from apps.learning.models import LearningProgress

from .models import Curriculum, Grade, Section, Subject, Topic
from .serializers import CurriculumSerializer, SubjectDetailSerializer, SubjectSerializer, TopicSerializer


def _resolve_grade(request) -> Grade:
    """Grade comes from the student's own profile unless an explicit ``grade`` id is given."""
    grade_param = request.query_params.get("grade")
    if grade_param:
        try:
            return Grade.objects.select_related("curriculum").get(pk=int(grade_param))
        except (Grade.DoesNotExist, ValueError):
            raise DomainError("Класс не найден.", code="not_found", status_code=404)
    student = _student_in_scope(request)
    if student is None:
        raise DomainError("Укажите параметр grade.", code="validation_error", status_code=400)
    return student.grade


@extend_schema(tags=["curriculum"])
class CurriculumListView(ListAPIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = CurriculumSerializer
    pagination_class = None
    queryset = Curriculum.objects.filter(is_active=True).prefetch_related("grades")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = self.request.query_params.get("lang", "ru")
        return ctx


@extend_schema(
    tags=["curriculum"],
    parameters=[OpenApiParameter("grade", int, description="ID класса; по умолчанию класс ученика")],
)
class SubjectListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = SubjectSerializer
    pagination_class = None

    def get_queryset(self):
        grade = _resolve_grade(self.request)
        return (
            Subject.objects.filter(
                curriculum=grade.curriculum,
                is_active=True,
                grade_from__lte=grade.number,
                grade_to__gte=grade.number,
            )
            .annotate(
                topics_count=Count(
                    "sections__topics",
                    filter=Q(sections__grade=grade, sections__topics__is_active=True),
                    distinct=True,
                )
            )
            .order_by("order", "name_ru")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _lang(self.request)
        return ctx


@extend_schema(tags=["curriculum"], parameters=[OpenApiParameter("grade", int)])
class SubjectDetailView(RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = SubjectDetailSerializer
    lookup_field = "slug"

    def get_object(self):
        grade = _resolve_grade(self.request)
        subject = get_object_or_404(
            Subject, slug=self.kwargs["slug"], curriculum=grade.curriculum, is_active=True
        )
        if not subject.available_for(grade.number):
            raise Http404
        subject.grade = grade
        self._sections = list(
            Section.objects.filter(subject=subject, grade=grade)
            .prefetch_related(
                Prefetch("topics", queryset=Topic.objects.filter(is_active=True).order_by("order"))
            )
            .order_by("order")
        )
        return subject

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _lang(self.request)
        ctx["sections"] = getattr(self, "_sections", [])
        student = _student_in_scope(self.request)
        if student is not None:
            topic_ids = [t.id for s in ctx["sections"] for t in s.topics.all()]
            ctx["progress_by_topic"] = dict(
                LearningProgress.objects.filter(student=student, topic_id__in=topic_ids).values_list(
                    "topic_id", "status"
                )
            )
        return ctx


@extend_schema(
    tags=["curriculum"],
    parameters=[
        OpenApiParameter("subject", str, description="slug предмета"),
        OpenApiParameter("grade", int),
    ],
)
class TopicListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TopicSerializer
    pagination_class = None

    def get_queryset(self):
        grade = _resolve_grade(self.request)
        qs = Topic.objects.filter(section__grade=grade, is_active=True).select_related("section__subject")
        subject_slug = self.request.query_params.get("subject")
        if subject_slug:
            qs = qs.filter(section__subject__slug=subject_slug)
        return qs.order_by("section__subject__order", "section__order", "order")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _lang(self.request)
        return ctx


def _topic_progress(topic: Topic, student, lang: str) -> dict:
    """Progress block of the topic screen; honest zeros when the child has not touched the topic."""
    empty = {"progress_status": "not_started", "progress": None, "last_quiz": None, "recent_sessions": []}
    if student is None:
        return empty
    from apps.quizzes.models import QuizAttempt
    from apps.tutor.models import LearningSession
    from apps.tutor.serializers import SessionSummarySerializer

    progress = LearningProgress.objects.filter(student=student, topic=topic).first()
    last = (
        QuizAttempt.objects.filter(student=student, quiz__topic=topic, status=QuizAttempt.Status.FINISHED)
        .order_by("-finished_at")
        .first()
    )
    sessions = (
        LearningSession.objects.filter(student=student, topic=topic)
        .select_related("subject", "topic", "assignment")
        .order_by("-last_activity_at")[:3]
    )
    progress_block = None
    if progress is not None:
        progress_block = {
            "sessions_count": progress.sessions_count,
            "attempts_count": progress.attempts_count,
            "correct_count": progress.correct_count,
            "hints_count": progress.hints_count,
            "last_activity_at": progress.last_activity_at,
        }
    quiz_block = None
    if last is not None:
        quiz_block = {
            "id": str(last.id),
            "correct_count": last.correct_count,
            "total_count": last.total_count,
            "score": round(last.correct_count / last.total_count, 3) if last.total_count else 0.0,
            "finished_at": last.finished_at,
        }
    return {
        "progress_status": progress.status if progress else "not_started",
        "progress": progress_block,
        "last_quiz": quiz_block,
        "recent_sessions": SessionSummarySerializer(sessions, many=True, context={"lang": lang}).data,
    }


@extend_schema(tags=["curriculum"])
class TopicDetailView(RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = TopicSerializer
    queryset = Topic.objects.filter(is_active=True).select_related("section__subject", "section__grade")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _lang(self.request)
        return ctx

    def retrieve(self, request, *args, **kwargs):
        topic = self.get_object()
        data = self.get_serializer(topic).data
        lang = _lang(request)
        data["subject"] = SubjectSerializer(topic.section.subject, context={"lang": lang}).data
        data["section"] = {"id": topic.section.id, "name": topic.section.name(lang)}
        data["grade"] = {"id": topic.section.grade.id, "number": topic.section.grade.number}
        data.update(_topic_progress(topic, _student_in_scope(request), lang))
        return Response(data)
