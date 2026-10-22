from django.urls import path

from .views import AppMetaView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("meta/", AppMetaView.as_view(), name="meta"),
]
