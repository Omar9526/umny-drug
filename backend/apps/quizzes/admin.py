from django.contrib import admin

from .models import Question, Quiz, QuizAttempt


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "topic", "grade", "language", "is_active")
    list_filter = ("grade__number", "language", "is_active")
    search_fields = ("name_ru", "name_ky")
    autocomplete_fields = ("topic",)
    inlines = (QuestionInline,)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("quiz", "student", "mode", "status", "correct_count", "total_count", "started_at")
    list_filter = ("mode", "status")
