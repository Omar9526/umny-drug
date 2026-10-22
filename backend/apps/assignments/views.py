from __future__ import annotations

from django.conf import settings
from django.http import FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import StudentProfile
from apps.core.exceptions import DomainError
from apps.core.permissions import IsStudent
from apps.tutor.serializers import SessionSummarySerializer

from . import services
from .models import Assignment, AssignmentImage, AssignmentUpload
from .serializers import (
    AssignmentDetailSerializer,
    ConfirmSerializer,
    UploadCreateSerializer,
    UploadSerializer,
)


def _student(request) -> StudentProfile:
    return get_object_or_404(
        StudentProfile.objects.select_related("grade", "curriculum", "user"), user=request.user
    )


def _ctx(request, student: StudentProfile) -> dict:
    return {"request": request, "lang": student.explanation_language, "student": student}


@extend_schema(tags=["assignments"], request=UploadCreateSerializer, responses={201: UploadSerializer})
class UploadCreateView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)
    parser_classes = (MultiPartParser, FormParser)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "upload"

    def post(self, request):
        student = _student(request)
        serializer = UploadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["source"] != "text" and not student.allow_photo_upload:
            raise DomainError(
                "Родители отключили загрузку фото. Можно написать задание текстом.",
                code="feature_disabled",
                status_code=403,
            )
        upload = services.create_upload(
            student=student,
            source=data["source"],
            files=request.FILES.getlist("images"),
            typed_text=data.get("typed_text", ""),
            language_hint=data.get("language_hint") or student.instruction_language,
            request=request,
        )
        services.enqueue_recognition(upload)
        upload.refresh_from_db()
        return Response(
            UploadSerializer(upload, context=_ctx(request, student)).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["assignments"], responses={200: UploadSerializer})
class UploadDetailView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def get(self, request, pk):
        student = _student(request)
        upload = get_object_or_404(
            AssignmentUpload.objects.prefetch_related("images"), pk=pk, student=student
        )
        return Response(UploadSerializer(upload, context=_ctx(request, student)).data)


@extend_schema(tags=["assignments"], request=None, responses={200: UploadSerializer})
class UploadRetryView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "upload"

    def post(self, request, pk):
        student = _student(request)
        upload = get_object_or_404(AssignmentUpload, pk=pk, student=student)
        services.retry_upload(upload)
        upload.refresh_from_db()
        return Response(UploadSerializer(upload, context=_ctx(request, student)).data)


@extend_schema(tags=["assignments"], responses={200: bytes})
class ImageView(APIView):
    """Serve a private upload image to a member of its family only."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        user = request.user
        qs = AssignmentImage.objects.select_related("upload")
        if not user.is_admin_role:
            qs = qs.filter(upload__family_id=user.family_id)
            if getattr(user, "role", "") == "student":  # siblings do not see each other's photos
                qs = qs.filter(upload__student__user=user)
        image = get_object_or_404(qs, pk=pk)
        if not image.is_available:
            return Response({"error": {"code": "gone", "message": "Срок хранения фото истёк."}}, status=410)
        if settings.STORAGE_BACKEND == "s3":
            return HttpResponseRedirect(image.file.url)
        response = FileResponse(image.file.open("rb"), content_type=image.mime_type)
        response["Cache-Control"] = "private, max-age=300"
        response["X-Content-Type-Options"] = "nosniff"
        return response


@extend_schema(tags=["assignments"], responses={200: AssignmentDetailSerializer})
class AssignmentDetailView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)

    def get(self, request, pk):
        student = _student(request)
        assignment = get_object_or_404(
            Assignment.objects.select_related("subject", "topic__section", "grade", "upload"),
            pk=pk,
            student=student,
        )
        return Response(AssignmentDetailSerializer(assignment, context=_ctx(request, student)).data)


@extend_schema(tags=["assignments"], request=ConfirmSerializer, responses={200: dict})
class AssignmentConfirmView(APIView):
    permission_classes = (IsAuthenticated, IsStudent)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "ai"

    def post(self, request, pk):
        student = _student(request)
        assignment = get_object_or_404(
            Assignment.objects.select_related(
                "subject", "topic__section", "grade", "upload", "student__user"
            ),
            pk=pk,
            student=student,
        )
        serializer = ConfirmSerializer(data=request.data, context={"student": student})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assignment, session = services.confirm_assignment(
            assignment=assignment,
            confirmed_text=data["confirmed_text"],
            subject=data["subject"],
            topic=data["topic"],
            subject_provided=data.get("subject_provided", False),
            request=request,
        )
        ctx = _ctx(request, student)
        return Response(
            {
                "assignment": AssignmentDetailSerializer(assignment, context=ctx).data,
                "session": SessionSummarySerializer(session, context=ctx).data,
            }
        )
