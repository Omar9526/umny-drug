from django.urls import path

from .views import QuizAnswerView, QuizAttemptView, QuizFinishView, QuizStartView

urlpatterns = [
    path("quizzes/start/", QuizStartView.as_view(), name="quiz-start"),
    path("quizzes/attempts/<uuid:pk>/", QuizAttemptView.as_view(), name="quiz-attempt"),
    path("quizzes/attempts/<uuid:pk>/answer/", QuizAnswerView.as_view(), name="quiz-answer"),
    path("quizzes/attempts/<uuid:pk>/finish/", QuizFinishView.as_view(), name="quiz-finish"),
]
