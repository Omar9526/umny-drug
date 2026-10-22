from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import DomainError
from apps.core.permissions import FamilyScopedQuerysetMixin, IsStudentOrParent
from apps.core.scope import request_lang, student_in_scope
from apps.curriculum.models import Grade, Subject
from apps.tutor.models import LearningSession
from apps.tutor.serializers import SessionSummarySerializer

from .services import knowledge_map


@extend_schema(
    tags=["learning"],
    parameters=[
        OpenApiParameter("status", str, description="active | completed | abandoned"),
        OpenApiParameter("subject", str, description="slug предмета"),
        OpenApiParameter("student", str, description="ID ребёнка (только для родителя)"),
    ],
)
class HistoryView(FamilyScopedQuerysetMixin, ListAPIView):
    """Learning history. Students see their own sessions; parents see their children's."""

    permission_classes = (IsAuthenticated, IsStudentOrParent)
    serializer_class = SessionSummarySerializer
    family_lookup = "family"

    def get_queryset(self):
        user = self.request.user
        qs = LearningSession.objects.select_related("subject", "topic", "assignment")
        qs = self.scope_to_family(qs)
        if user.is_student:
            qs = qs.filter(student__user=user)
        else:
            student_id = self.request.query_params.get("student")
            if student_id:
                qs = qs.filter(student_id=student_id)
        status_param = self.request.query_params.get("status")
        if status_param:
            if status_param not in LearningSession.Status.values:
                raise DomainError("Неизвестный статус.", code="validation_error", status_code=400)
            qs = qs.filter(status=status_param)
        subject = self.request.query_params.get("subject")
        if subject:
            qs = qs.filter(subject__slug=subject)
        return qs.order_by("-last_activity_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = getattr(self.request.user, "preferred_language", "ru")
        return ctx


@extend_schema(
    tags=["learning"],
    parameters=[
        OpenApiParameter("subject", str, description="slug предмета", required=True),
        OpenApiParameter("grade", int, description="ID класса; по умолчанию класс ученика"),
        OpenApiParameter("student", str, description="ID ребёнка (только для родителя)"),
    ],
)
class KnowledgeMapView(APIView):
    """Route through a subject with per-topic status. Students see their own map; parents a child's."""

    permission_classes = (IsAuthenticated, IsStudentOrParent)

    def get(self, request):
        student = student_in_scope(request)
        if student is None:
            raise DomainError("Ученик не найден.", code="not_found", status_code=404)
        slug = request.query_params.get("subject")
        if not slug:
            raise DomainError("Укажите параметр subject.", code="validation_error", status_code=400)
        grade = student.grade
        grade_param = request.query_params.get("grade")
        if grade_param:
            grade = get_object_or_404(
                Grade.objects.select_related("curriculum"),
                pk=grade_param,
                curriculum=student.grade.curriculum,
            )
        subject = get_object_or_404(Subject, slug=slug, curriculum=grade.curriculum, is_active=True)
        if not subject.available_for(grade.number):
            raise DomainError("Предмет недоступен для этого класса.", code="not_found", status_code=404)
        return Response(
            knowledge_map(student=student, subject=subject, grade=grade, lang=request_lang(request))
        )
