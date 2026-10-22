from django.urls import path

from .views import (
    AssignmentConfirmView,
    AssignmentDetailView,
    ImageView,
    UploadCreateView,
    UploadDetailView,
    UploadRetryView,
)

urlpatterns = [
    path("upload/", UploadCreateView.as_view(), name="assignment-upload"),
    path("uploads/<uuid:pk>/", UploadDetailView.as_view(), name="assignment-upload-detail"),
    path("uploads/<uuid:pk>/retry/", UploadRetryView.as_view(), name="assignment-upload-retry"),
    path("images/<uuid:pk>/", ImageView.as_view(), name="assignment-image"),
    path("<uuid:pk>/", AssignmentDetailView.as_view(), name="assignment-detail"),
    path("<uuid:pk>/confirm/", AssignmentConfirmView.as_view(), name="assignment-confirm"),
]
