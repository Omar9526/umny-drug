from django.urls import path

from .views import HistoryView, KnowledgeMapView

urlpatterns = [
    path("learning/history/", HistoryView.as_view(), name="learning-history"),
    path("learning/map/", KnowledgeMapView.as_view(), name="learning-map"),
]
