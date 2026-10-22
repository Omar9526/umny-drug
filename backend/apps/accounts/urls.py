from django.urls import path

from .views import (
    ChildLoginView,
    ChildLookupView,
    LoginView,
    LogoutView,
    MeView,
    ParentRegisterView,
    RefreshView,
)

urlpatterns = [
    path("parent/register/", ParentRegisterView.as_view(), name="auth-parent-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("token/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("child/lookup/", ChildLookupView.as_view(), name="auth-child-lookup"),
    path("child/login/", ChildLoginView.as_view(), name="auth-child-login"),
    path("me/", MeView.as_view(), name="auth-me"),
]
