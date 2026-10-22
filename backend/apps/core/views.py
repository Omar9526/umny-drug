from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.registry import provider_status
from apps.core.permissions import IsAdminRole


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
        cache_ok = True
        try:
            cache.set("healthcheck", "1", timeout=10)
            cache_ok = cache.get("healthcheck") == "1"
        except Exception:  # pragma: no cover - only on infrastructure failure
            cache_ok = False
        ok = db_ok and cache_ok
        return Response(
            {"status": "ok" if ok else "degraded", "database": db_ok, "cache": cache_ok},
            status=200 if ok else 503,
        )


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


@extend_schema(tags=["admin"], responses={200: dict})
class AIUsageSummaryView(APIView):
    """Spend and call counts for operators: today vs. budget, last 7 days, split by purpose/provider.

    Only aggregates leave the server — no prompts, no children's data.
    """

    permission_classes = (IsAuthenticated, IsAdminRole)

    def get(self, request):
        from apps.tutor.models import AIUsage

        now = timezone.localtime()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = day_start - timezone.timedelta(days=6)
        today = AIUsage.objects.filter(created_at__gte=day_start)
        totals = today.aggregate(cost=Sum("cost_usd"), calls=Count("id"))
        budget = float(getattr(settings, "AI_DAILY_BUDGET_USD", 0) or 0)
        spent = float(totals["cost"] or 0)

        def split(field: str) -> list[dict]:
            rows = today.values(field).annotate(cost=Sum("cost_usd"), calls=Count("id")).order_by("-cost")
            return [{field: r[field], "cost_usd": float(r["cost"] or 0), "calls": r["calls"]} for r in rows]

        days = (
            AIUsage.objects.filter(created_at__gte=week_start)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(cost=Sum("cost_usd"), calls=Count("id"))
            .order_by("day")
        )
        top_families = (
            today.exclude(family__isnull=True)
            .values("family_id")
            .annotate(cost=Sum("cost_usd"), calls=Count("id"))
            .order_by("-cost")[:5]
        )
        return Response(
            {
                "today": {
                    "cost_usd": round(spent, 4),
                    "calls": totals["calls"],
                    "budget_usd": budget,
                    "share": round(spent / budget, 3) if budget else None,
                    "alert_threshold": float(getattr(settings, "AI_BUDGET_ALERT_THRESHOLD", 0.8)),
                },
                "last_7_days": [
                    {"date": r["day"].isoformat(), "cost_usd": float(r["cost"] or 0), "calls": r["calls"]}
                    for r in days
                ],
                "by_purpose_today": split("purpose"),
                "by_provider_today": split("provider"),
                "by_model_today": split("model"),
                "top_families_today": [
                    {"family_id": str(r["family_id"]), "cost_usd": float(r["cost"] or 0), "calls": r["calls"]}
                    for r in top_families
                ],
            }
        )
