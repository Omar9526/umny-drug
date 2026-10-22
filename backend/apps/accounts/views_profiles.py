from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.registry import provider_status
from apps.core.permissions import IsStudent
from apps.curriculum.models import Subject
from apps.curriculum.serializers import SubjectSerializer
from apps.tutor.models import LearningSession
from apps.tutor.serializers import SessionSummarySerializer

from .models import StudentProfile
from .serializers import StudentProfileSerializer, StudentProfileUpdateSerializer


def _student_for(request) -> StudentProfile:
    return get_object_or_404(
        StudentProfile.objects.select_related("grade", "curriculum", "user"), user=request.user
    )


@extend_schema(tags=["students"], responses={200: StudentProfileSerializer})
class StudentMeView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def get(self, request):
        return Response(StudentProfileSerializer(_student_for(request)).data)

    @extend_schema(request=StudentProfileUpdateSerializer, responses={200: StudentProfileSerializer})
    def patch(self, request):
        student = _student_for(request)
        serializer = StudentProfileUpdateSerializer(student, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StudentProfileSerializer(student).data)


@extend_schema(tags=["students"], responses={200: dict})
class StudentDashboardView(APIView):
    """Everything the home screen needs in one round-trip. All numbers are real aggregates."""

    permission_classes = (IsAuthenticated, IsStudent)

    def get(self, request):
        student = _student_for(request)
        lang = student.explanation_language
        sessions = LearningSession.objects.filter(student=student).select_related(
            "subject", "topic", "assignment"
        )

        continue_session = (
            sessions.filter(status=LearningSession.Status.ACTIVE).order_by("-last_activity_at").first()
        )
        recent = sessions.order_by("-last_activity_at")[:5]

        week_start = timezone.now() - timedelta(days=7)
        totals = sessions.aggregate(
            sessions_total=Count("id"),
            completed_total=Count("id", filter=Q(status=LearningSession.Status.COMPLETED)),
            week_sessions=Count("id", filter=Q(created_at__gte=week_start)),
            week_independent=Count(
                "id",
                filter=Q(
                    created_at__gte=week_start,
                    outcome=LearningSession.Outcome.UNDERSTOOD_INDEPENDENTLY,
                ),
            ),
        )

        subjects = (
            Subject.objects.filter(
                curriculum=student.curriculum,
                is_active=True,
                grade_from__lte=student.grade.number,
                grade_to__gte=student.grade.number,
            )
            .annotate(
                topics_count=Count(
                    "sections__topics",
                    filter=Q(sections__grade=student.grade, sections__topics__is_active=True),
                    distinct=True,
                )
            )
            .order_by("order", "name_ru")
        )

        return Response(
            {
                "student": StudentProfileSerializer(student).data,
                "demo_mode": provider_status()["demo_mode"],
                "continue_session": SessionSummarySerializer(continue_session, context={"lang": lang}).data
                if continue_session
                else None,
                "recent_sessions": SessionSummarySerializer(recent, many=True, context={"lang": lang}).data,
                "subjects": SubjectSerializer(subjects, many=True, context={"lang": lang}).data,
                "stats": totals,
            }
        )
