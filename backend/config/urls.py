from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1 = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.accounts.urls_profiles")),
    path("", include("apps.curriculum.urls")),
    path("", include("apps.parents.urls")),
    path("", include("apps.learning.urls")),
    path("assignments/", include("apps.assignments.urls")),
    path("tutor/", include("apps.tutor.urls")),
    path("", include("apps.quizzes.urls")),
]

urlpatterns = [
    path(settings.ADMIN_URL_PATH, admin.site.urls),
    path("api/v1/", include((api_v1, "v1"), namespace="v1")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
