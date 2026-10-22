from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.registry import provider_status


@extend_schema(tags=["meta"], responses={200: dict})
class HealthView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()

    def get(self, request):
        db_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:  # pragma: no cover - only on infrastructure failure
            db_ok = False
        return Response({"status": "ok" if db_ok else "degraded", "database": db_ok})


@extend_schema(tags=["meta"], responses={200: dict})
class AppMetaView(APIView):
    """Public, non-sensitive runtime configuration consumed by the frontend."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request):
        ai = provider_status()
        return Response(
            {
                "environment": settings.ENVIRONMENT,
                "demo_mode": ai["demo_mode"],
                "ai_provider": ai["name"],
                "languages": [code for code, _ in settings.LANGUAGES],
                "upload": {
                    "max_image_mb": settings.MAX_UPLOAD_IMAGE_MB,
                    "max_images": settings.MAX_UPLOAD_IMAGES_PER_ASSIGNMENT,
                    "accepted_types": ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"],
                },
                "consent_version": settings.CONSENT_TERMS_VERSION,
            }
        )
