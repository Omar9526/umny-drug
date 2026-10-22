from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenBackendError, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.audit import audit
from apps.core.exceptions import DomainError
from apps.core.throttles import AuthRateThrottle, FamilyCodeThrottle

from . import services
from .models import StudentProfile, User
from .serializers import (
    AuthResponseSerializer,
    ChildLoginSerializer,
    ChildLookupSerializer,
    ChildPublicSerializer,
    LoginSerializer,
    ParentRegisterSerializer,
    UserSerializer,
)


def _auth_response(user: User, status_code: int = status.HTTP_200_OK) -> Response:
    access, refresh = services.issue_tokens(user)
    response = Response({"access": access, "user": UserSerializer(user).data}, status=status_code)
    services.set_refresh_cookie(response, refresh)
    return response


def _not_authenticated(message: str) -> Response:
    return Response(
        {"error": {"code": "not_authenticated", "message": message}}, status=status.HTTP_401_UNAUTHORIZED
    )


def _reused_token_owner(raw: str):
    """Owner of a refresh token that was already rotated or revoked and shows up again.

    That is the signature of a copied cookie: the legitimate browser holds the rotated token, so
    whoever still presents the old one is not that browser. A short grace window covers two tabs
    refreshing at the same moment. Expired or forged tokens are not a reuse signal.
    """
    try:
        payload = token_backend.decode(raw, verify=True)
    except TokenBackendError:
        return None
    row = BlacklistedToken.objects.filter(token__jti=payload.get("jti")).select_related("token__user").first()
    if row is None:
        return None
    grace = timedelta(seconds=settings.AUTH_REFRESH_REUSE_GRACE_SECONDS)
    if timezone.now() - row.blacklisted_at < grace:
        return None
    return row.token.user


def _check_origin(request) -> None:
    """Cookie-authenticated endpoints must only be called from our own origins (CSRF defence)."""
    origin = request.headers.get("Origin")
    if origin and origin not in settings.CORS_ALLOWED_ORIGINS:
        raise DomainError("Запрос с недопустимого источника.", code="permission_denied", status_code=403)


@extend_schema(tags=["auth"], request=ParentRegisterSerializer, responses={201: AuthResponseSerializer})
class ParentRegisterView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (AuthRateThrottle,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = ParentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = services.register_parent(
            display_name=data["display_name"],
            email=data["email"],
            password=data["password"],
            preferred_language=data["preferred_language"],
            consents=data["consents"],
            request=request,
        )
        return _auth_response(user, status.HTTP_201_CREATED)


@extend_schema(tags=["auth"], request=LoginSerializer, responses={200: AuthResponseSerializer})
class LoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (AuthRateThrottle,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        audit("parent.login", actor=user, request=request)
        return _auth_response(user)


@extend_schema(tags=["auth"], request=None, responses={200: AuthResponseSerializer, 401: OpenApiResponse()})
class RefreshView(APIView):
    """Rotate the refresh cookie and return a fresh access token plus the current user.

    An invalid or already-rotated token answers 401 *without* deleting the cookie: a second tab
    that lost the race keeps the cookie the first tab just received. Only logout clears it.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "refresh"

    def post(self, request):
        _check_origin(request)
        raw = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not raw:
            return _not_authenticated("Сессия не найдена.")
        serializer = TokenRefreshSerializer(data={"refresh": raw})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken):
            owner = _reused_token_owner(raw)
            if owner is not None:
                # Reuse detected: nobody can tell which holder is the thief, so every session ends.
                services.revoke_user_sessions(owner)
                audit("auth.refresh_reuse_detected", actor=owner, target=owner, request=request)
                response = Response(
                    {
                        "error": {
                            "code": "session_revoked",
                            "message": "Сессия отозвана из соображений безопасности. Войди снова.",
                        }
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
                services.clear_refresh_cookie(response)
                return response
            return _not_authenticated("Сессия истекла. Войди снова.")

        access = serializer.validated_data["access"]
        new_refresh = serializer.validated_data.get("refresh")
        token = RefreshToken(new_refresh) if new_refresh else RefreshToken(raw)
        user = (
            User.objects.select_related(
                "student_profile__grade", "student_profile__curriculum", "parent_profile__family"
            )
            .filter(id=token["user_id"], is_active=True)
            .first()
        )
        if user is None:
            response = _not_authenticated("Аккаунт недоступен.")
            services.clear_refresh_cookie(response)
            return response
        response = Response({"access": access, "user": UserSerializer(user).data})
        if new_refresh:
            services.set_refresh_cookie(response, new_refresh)
        return response


@extend_schema(tags=["auth"], request=None, responses={204: None})
class LogoutView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()

    def post(self, request):
        _check_origin(request)
        raw = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        response = Response(status=status.HTTP_204_NO_CONTENT)
        services.clear_refresh_cookie(response)
        return response


@extend_schema(
    tags=["auth"], request=ChildLookupSerializer, responses={200: ChildPublicSerializer(many=True)}
)
class ChildLookupView(APIView):
    """Step 1 of child login: the family code reveals only nicknames and avatars."""

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (FamilyCodeThrottle, AuthRateThrottle)
    throttle_scope = "auth"

    def post(self, request):
        serializer = ChildLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        family = services.lookup_family(serializer.validated_data["family_code"])
        children = (
            StudentProfile.objects.filter(family=family, is_active=True, user__is_active=True)
            .select_related("grade")
            .order_by("created_at")
        )
        return Response(
            {
                "family": {"display_code": family.display_code},
                "children": ChildPublicSerializer(children, many=True).data,
            }
        )


@extend_schema(tags=["auth"], request=ChildLoginSerializer, responses={200: AuthResponseSerializer})
class ChildLoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (FamilyCodeThrottle, AuthRateThrottle)
    throttle_scope = "child_login"

    def post(self, request):
        serializer = ChildLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        student = services.authenticate_child(
            family_code=data["family_code"], student_id=data["student_id"], pin=data["pin"], request=request
        )
        return _auth_response(student.user)


@extend_schema(tags=["auth"], responses={200: UserSerializer})
class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)
