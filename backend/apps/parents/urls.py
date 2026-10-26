from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    ChildrenViewSet,
    ConsentListView,
    ConsentRevokeView,
    FamilyDeleteView,
    FamilyRotateCodeView,
    FamilySettingsView,
    FamilyView,
    NotificationListView,
    NotificationReadView,
    OverviewView,
    PushConfigView,
    PushSubscriptionView,
)

router = SimpleRouter()
router.register("parents/children", ChildrenViewSet, basename="parent-children")

urlpatterns = [
    path("parents/overview/", OverviewView.as_view(), name="parent-overview"),
    path("parents/family/", FamilyView.as_view(), name="parent-family"),
    path("parents/family/rotate-code/", FamilyRotateCodeView.as_view(), name="parent-family-rotate"),
    path("parents/family/delete/", FamilyDeleteView.as_view(), name="parent-family-delete"),
    path("parents/settings/", FamilySettingsView.as_view(), name="parent-settings"),
    path("parents/notifications/", NotificationListView.as_view(), name="parent-notifications"),
    path(
        "parents/notifications/read-all/",
        NotificationReadView.as_view(),
        name="parent-notifications-read-all",
    ),
    path(
        "parents/notifications/<uuid:pk>/read/",
        NotificationReadView.as_view(),
        name="parent-notification-read",
    ),
    path("parents/push/", PushConfigView.as_view(), name="parent-push-config"),
    path("parents/push/subscriptions/", PushSubscriptionView.as_view(), name="parent-push-subscriptions"),
    path("parents/consents/", ConsentListView.as_view(), name="parent-consents"),
    path("parents/consents/<uuid:pk>/revoke/", ConsentRevokeView.as_view(), name="parent-consent-revoke"),
    *router.urls,
]
