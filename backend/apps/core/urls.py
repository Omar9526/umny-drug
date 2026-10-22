from django.urls import path

from .views import AIUsageSummaryView, AppMetaView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("meta/", AppMetaView.as_view(), name="meta"),
    path("admin/ai-usage/", AIUsageSummaryView.as_view(), name="admin-ai-usage"),
]
