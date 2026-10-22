from django.urls import path

from .views import (
    CheckAnswerView,
    FlagMessageView,
    SessionCompleteView,
    SessionCreateView,
    SessionDetailView,
    SessionTurnView,
)

urlpatterns = [
    path("sessions/", SessionCreateView.as_view(), name="tutor-session-create"),
    path("sessions/<uuid:pk>/", SessionDetailView.as_view(), name="tutor-session-detail"),
    path("sessions/<uuid:pk>/messages/", SessionTurnView.as_view(), name="tutor-session-turn"),
    path("sessions/<uuid:pk>/check-answer/", CheckAnswerView.as_view(), name="tutor-session-check"),
    path("sessions/<uuid:pk>/complete/", SessionCompleteView.as_view(), name="tutor-session-complete"),
    path(
        "sessions/<uuid:pk>/messages/<uuid:message_id>/flag/",
        FlagMessageView.as_view(),
        name="tutor-message-flag",
    ),
]
