from django.urls import path

from .views import CurriculumListView, SubjectDetailView, SubjectListView, TopicDetailView, TopicListView

urlpatterns = [
    path("curricula/", CurriculumListView.as_view(), name="curriculum-list"),
    path("subjects/", SubjectListView.as_view(), name="subject-list"),
    path("subjects/<slug:slug>/", SubjectDetailView.as_view(), name="subject-detail"),
    path("topics/", TopicListView.as_view(), name="topic-list"),
    path("topics/<int:pk>/", TopicDetailView.as_view(), name="topic-detail"),
]
