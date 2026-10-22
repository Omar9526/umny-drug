from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import StudentProfile
from apps.core.permissions import IsStudent
from apps.core.scope import request_lang
from apps.curriculum.models import Topic

from . import services
from .models import QuizAttempt
from .serializers import AnswerSerializer, QuizAttemptSerializer, StartQuizSerializer


def _student(request) -> StudentProfile:
    return get_object_or_404(
        StudentProfile.objects.select_related("grade__curriculum", "user", "family"), user=request.user
    )


def _attempt(request, pk, student: StudentProfile) -> QuizAttempt:
    qs = QuizAttempt.objects.select_related("quiz__topic__section__subject", "student")
    return get_object_or_404(qs, pk=pk, student=student)


def _ctx(request) -> dict:
    return {"lang": request_lang(request), "request": request}


@extend_schema(tags=["quizzes"], request=StartQuizSerializer, responses={201: QuizAttemptSerializer})
class QuizStartView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "ai"

    def post(self, request):
        student = _student(request)
        serializer = StartQuizSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = get_object_or_404(
            Topic.objects.select_related("section__grade__curriculum", "section__subject"),
            pk=serializer.validated_data["topic_id"],
            is_active=True,
        )
        attempt = services.start_quiz(student=student, topic=topic, request=request)
        return Response(
            QuizAttemptSerializer(attempt, context=_ctx(request)).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["quizzes"], responses={200: QuizAttemptSerializer})
class QuizAttemptView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def get(self, request, pk):
        student = _student(request)
        return Response(QuizAttemptSerializer(_attempt(request, pk, student), context=_ctx(request)).data)


@extend_schema(tags=["quizzes"], request=AnswerSerializer, responses={200: dict})
class QuizAnswerView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def post(self, request, pk):
        student = _student(request)
        attempt = _attempt(request, pk, student)
        serializer = AnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(
            services.answer_question(attempt=attempt, question_id=data["question_id"], answer=data["answer"])
        )


@extend_schema(tags=["quizzes"], request=None, responses={200: QuizAttemptSerializer})
class QuizFinishView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def post(self, request, pk):
        student = _student(request)
        attempt = services.finish_quiz(attempt=_attempt(request, pk, student), request=request)
        attempt = _attempt(request, attempt.pk, student)
        return Response(QuizAttemptSerializer(attempt, context=_ctx(request)).data)
