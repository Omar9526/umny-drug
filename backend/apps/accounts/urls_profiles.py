from django.urls import path

from .views_profiles import StudentDashboardView, StudentMeView

urlpatterns = [
    path("students/me/", StudentMeView.as_view(), name="student-me"),
    path("students/me/dashboard/", StudentDashboardView.as_view(), name="student-dashboard"),
]
