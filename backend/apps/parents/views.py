from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.accounts import services as account_services
from apps.accounts.models import ConsentRecord, ParentProfile
from apps.accounts.serializers import (
    ChildCreateSerializer,
    ChildPinSerializer,
    ChildUpdateSerializer,
    ConsentRecordSerializer,
    FamilySerializer,
    StudentProfileSerializer,
)
from apps.core.pagination import DefaultPagination
from apps.core.permissions import IsParent
from apps.tutor.models import LearningSession
from apps.tutor.queries import session_queryset
from apps.tutor.serializers import SessionDetailSerializer, SessionSummarySerializer

from . import services
from .models import ParentNotification
from .serializers import (
    ChildProgressSerializer,
    FamilyDeleteSerializer,
    FamilySettingsSerializer,
    NotificationSerializer,
    OverviewSerializer,
)


def _parent_for(request) -> ParentProfile:
    return get_object_or_404(ParentProfile.objects.select_related("family", "user"), user=request.user)


@extend_schema(tags=["parents"])
class ChildrenViewSet(ViewSet):
    """Children of the calling parent's family. Lookups are always scoped by family (no IDOR)."""

    permission_classes = (IsAuthenticated, IsParent)

    @extend_schema(responses={200: StudentProfileSerializer(many=True)})
    def list(self, request):
        parent = _parent_for(request)
        return Response(StudentProfileSerializer(services.children_of(parent), many=True).data)

    @extend_schema(request=ChildCreateSerializer, responses={201: StudentProfileSerializer})
    def create(self, request):
        parent = _parent_for(request)
        serializer = ChildCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        student = account_services.create_child(
            parent=parent,
            nickname=data["nickname"],
            grade=data["grade_id"],
            instruction_language=data["instruction_language"],
            explanation_language=data["explanation_language"],
            avatar=data["avatar"],
            pin=data["pin"],
            consent_confirmed=data["consent_confirmed"],
            request=request,
        )
        return Response(StudentProfileSerializer(student).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: StudentProfileSerializer})
    def retrieve(self, request, pk=None):
        parent = _parent_for(request)
        return Response(StudentProfileSerializer(services.child_for(parent, pk)).data)

    @extend_schema(request=ChildUpdateSerializer, responses={200: StudentProfileSerializer})
    def partial_update(self, request, pk=None):
        parent = _parent_for(request)
        student = services.child_for(parent, pk)
        serializer = ChildUpdateSerializer(student, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        account_services.update_child(
            parent=parent, student=student, data=serializer.validated_data, request=request
        )
        return Response(StudentProfileSerializer(student).data)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        parent = _parent_for(request)
        student = services.child_for(parent, pk)
        account_services.deactivate_child(parent=parent, student=student, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=ChildPinSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="pin")
    def set_pin(self, request, pk=None):
        parent = _parent_for(request)
        student = services.child_for(parent, pk)
        serializer = ChildPinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account_services.reset_child_pin(
            parent=parent, student=student, pin=serializer.validated_data["pin"], request=request
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={200: ChildProgressSerializer})
    @action(detail=True, methods=["get"], url_path="progress")
    def progress(self, request, pk=None):
        parent = _parent_for(request)
        student = services.child_for(parent, pk)
        data = services.child_progress(student)
        data["child"] = student
        return Response(ChildProgressSerializer(data, context={"lang": student.explanation_language}).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("outcome", str),
            OpenApiParameter("subject", str),
        ],
        responses={200: SessionSummarySerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="sessions")
    def sessions(self, request, pk=None):
        parent = _parent_for(request)
        student = services.child_for(parent, pk)
        qs = session_queryset().filter(student=student)
        status_param = request.query_params.get("status")
        if status_param in LearningSession.Status.values:
            qs = qs.filter(status=status_param)
        outcome = request.query_params.get("outcome")
        if outcome in LearningSession.Outcome.values:
            qs = qs.filter(outcome=outcome)
        subject = request.query_params.get("subject")
        if subject:
            qs = qs.filter(subject__slug=subject)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(qs.order_by("-last_activity_at"), request, view=self)
        data = SessionSummarySerializer(page, many=True, context={"lang": student.explanation_language}).data
        return paginator.get_paginated_response(data)

    @extend_schema(responses={200: SessionDetailSerializer})
    @action(detail=True, methods=["get"], url_path=r"sessions/(?P<session_id>[0-9a-f-]+)")
    def session_detail(self, request, pk=None, session_id=None):
        """Transparency rule: the dialogue is visible only when the child's profile allows it;
        outcomes, attempts and the summary are always visible to the parent."""
        parent = _parent_for(request)
        student = services.child_for(parent, pk)
        session = get_object_or_404(session_queryset(detail=True), pk=session_id, student=student)
        data = SessionDetailSerializer(session, context={"lang": student.explanation_language}).data
        data["conversation_visible"] = student.share_conversations_with_parent
        data["summary_for_parent"] = session.summary_for_parent
        if not student.share_conversations_with_parent:
            data["messages"] = []
        return Response(data)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="erase")
    def erase(self, request, pk=None):
        parent = _parent_for(request)
        student = services.child_for(parent, pk)
        counts = services.erase_child_data(parent=parent, student=student, request=request)
        return Response({"erased": counts})


@extend_schema(tags=["parents"], responses={200: OverviewSerializer})
class OverviewView(APIView):
    permission_classes = (IsAuthenticated, IsParent)

    def get(self, request):
        parent = _parent_for(request)
        children = [
            {"child": child, "summary": services.child_summary(child)}
            for child in services.children_of(parent)
        ]
        payload = {
            "children": children,
            "unread_notifications": ParentNotification.objects.filter(
                parent=parent, read_at__isnull=True
            ).count(),
            "family_code": parent.family.display_code,
        }
        return Response(OverviewSerializer(payload).data)


@extend_schema(tags=["parents"], responses={200: FamilySerializer})
class FamilyView(APIView):
    permission_classes = (IsAuthenticated, IsParent)

    def get(self, request):
        return Response(FamilySerializer(_parent_for(request).family).data)


@extend_schema(tags=["parents"], request=None, responses={200: FamilySerializer})
class FamilyRotateCodeView(APIView):
    permission_classes = (IsAuthenticated, IsParent)

    def post(self, request):
        parent = _parent_for(request)
        account_services.rotate_family_code(parent=parent, request=request)
        parent.family.refresh_from_db()
        return Response(FamilySerializer(parent.family).data)


@extend_schema(tags=["parents"], responses={200: FamilySettingsSerializer})
class FamilySettingsView(APIView):
    permission_classes = (IsAuthenticated, IsParent)

    def get(self, request):
        return Response(FamilySettingsSerializer(_parent_for(request)).data)

    @extend_schema(request=FamilySettingsSerializer)
    def patch(self, request):
        parent = _parent_for(request)
        serializer = FamilySettingsSerializer(parent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(FamilySettingsSerializer(parent).data)


@extend_schema(tags=["parents"], request=FamilyDeleteSerializer, responses={200: dict})
class FamilyDeleteView(APIView):
    permission_classes = (IsAuthenticated, IsParent)

    def post(self, request):
        parent = _parent_for(request)
        serializer = FamilyDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.delete_family(
            parent=parent, password=serializer.validated_data["password"], request=request
        )
        response = Response(result)
        account_services.clear_refresh_cookie(response)
        return response


@extend_schema(tags=["parents"], responses={200: NotificationSerializer(many=True)})
class NotificationListView(ListAPIView):
    permission_classes = (IsAuthenticated, IsParent)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        parent = _parent_for(self.request)
        qs = ParentNotification.objects.filter(parent=parent).select_related("student")
        if self.request.query_params.get("unread") == "1":
            qs = qs.filter(read_at__isnull=True)
        return qs.order_by("-created_at")


@extend_schema(tags=["parents"], request=None, responses={200: dict})
class NotificationReadView(APIView):
    permission_classes = (IsAuthenticated, IsParent)

    def post(self, request, pk=None):
        parent = _parent_for(request)
        return Response({"updated": services.mark_read(parent, pk)})


def _family_consents(parent: ParentProfile):
    return ConsentRecord.objects.filter(granted_by__parent_profile__family=parent.family).select_related(
        "student"
    )


@extend_schema(tags=["parents"], responses={200: ConsentRecordSerializer(many=True)})
class ConsentListView(ListAPIView):
    permission_classes = (IsAuthenticated, IsParent)
    serializer_class = ConsentRecordSerializer
    pagination_class = None

    def get_queryset(self):
        return _family_consents(_parent_for(self.request)).order_by("-granted_at")


@extend_schema(tags=["parents"], request=None, responses={200: ConsentRecordSerializer})
class ConsentRevokeView(APIView):
    permission_classes = (IsAuthenticated, IsParent)

    def post(self, request, pk):
        parent = _parent_for(request)
        consent = get_object_or_404(_family_consents(parent), pk=pk)
        consent = services.revoke_consent(parent=parent, consent=consent, request=request)
        return Response(ConsentRecordSerializer(consent).data)
