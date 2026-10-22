from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import StudentProfile
from apps.core.exceptions import DomainError
from apps.core.permissions import IsStudent
from apps.core.sse import EventStreamRenderer, is_asgi, sse_response
from apps.curriculum.models import Subject, Topic

from . import services
from .models import LearningSession
from .queries import session_queryset
from .serializers import (
    AIMessageSerializer,
    CheckAnswerSerializer,
    CreateSessionSerializer,
    FlagSerializer,
    SessionDetailSerializer,
    SessionStateSerializer,
    TurnSerializer,
)


def _student(request) -> StudentProfile:
    return get_object_or_404(
        StudentProfile.objects.select_related("grade", "curriculum", "user"), user=request.user
    )


def _session(request, pk, student: StudentProfile, *, detail: bool = False) -> LearningSession:
    return get_object_or_404(session_queryset(detail=detail), pk=pk, student=student)


def _ctx(request, student: StudentProfile) -> dict:
    return {"request": request, "lang": student.explanation_language}


@extend_schema(tags=["tutor"], request=CreateSessionSerializer, responses={201: SessionDetailSerializer})
class SessionCreateView(APIView):
    """Start a session without a photo: a free question, a topic explanation, exam prep."""

    permission_classes = (IsAuthenticated, IsStudent)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "ai"

    def post(self, request):
        student = _student(request)
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not student.allow_free_questions:
            if data["mode"] in ("question", "check_answer"):
                raise DomainError(
                    "Родители ограничили свободные вопросы. Сфотографируй домашнее задание или выбери тему.",
                    code="feature_disabled",
                    status_code=403,
                )
            if not data.get(
                "topic_id"
            ):  # explain_topic / exam_prep / practice without a topic is a free chat
                raise DomainError(
                    "Родители ограничили свободные вопросы. Выбери тему на карте знаний.",
                    code="feature_disabled",
                    status_code=403,
                )
        subject = None
        topic = None
        if data.get("subject_slug"):
            subject = get_object_or_404(
                Subject.objects.filter(
                    curriculum=student.curriculum,
                    is_active=True,
                    grade_from__lte=student.grade.number,
                    grade_to__gte=student.grade.number,
                ),
                slug=data["subject_slug"],
            )
        if data.get("topic_id"):
            topic = get_object_or_404(
                Topic.objects.filter(section__grade=student.grade, is_active=True).select_related(
                    "section__subject"
                ),
                pk=data["topic_id"],
            )
        session = services.create_session(
            student=student,
            mode=data["mode"],
            subject=subject,
            topic=topic,
            question=data.get("question", ""),
            request=request,
        )
        session = _session(request, session.pk, student, detail=True)
        return Response(
            SessionDetailSerializer(session, context=_ctx(request, student)).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["tutor"], responses={200: SessionDetailSerializer})
class SessionDetailView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def get(self, request, pk):
        student = _student(request)
        session = _session(request, pk, student, detail=True)
        return Response(SessionDetailSerializer(session, context=_ctx(request, student)).data)


@extend_schema(tags=["tutor"], request=TurnSerializer, responses={200: bytes})
class SessionTurnView(APIView):
    """Streams the assistant's reply as Server-Sent Events: ``delta`` → … → ``final`` | ``error``."""

    permission_classes = (IsAuthenticated, IsStudent)
    renderer_classes = (EventStreamRenderer, JSONRenderer)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "ai"

    def post(self, request, pk):
        student = _student(request)
        session = _session(request, pk, student)
        serializer = TurnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        events = services.run_turn(
            session=session, command=data["command"], content=data["content"], request=request
        )
        return sse_response(events, asgi=is_asgi(request))


@extend_schema(tags=["tutor"], request=CheckAnswerSerializer, responses={200: dict})
class CheckAnswerView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "ai"

    def post(self, request, pk):
        student = _student(request)
        session = _session(request, pk, student)
        serializer = CheckAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.check_answer(
            session=session, answer_text=serializer.validated_data["answer_text"], request=request
        )
        return Response(result)


@extend_schema(tags=["tutor"], request=None, responses={200: SessionStateSerializer})
class SessionCompleteView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def post(self, request, pk):
        student = _student(request)
        session = _session(request, pk, student)
        session = services.complete_session(session=session, request=request)
        return Response(SessionStateSerializer(session).data)


@extend_schema(tags=["tutor"], request=FlagSerializer, responses={200: AIMessageSerializer})
class FlagMessageView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def post(self, request, pk, message_id):
        student = _student(request)
        session = _session(request, pk, student)
        serializer = FlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.flag_message(
            session=session,
            message_id=message_id,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(AIMessageSerializer(message).data)
