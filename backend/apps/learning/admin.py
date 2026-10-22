from django.contrib import admin

from .models import AnswerAttempt, KnowledgeMapNode, LearningProgress, VerificationResult


@admin.register(AnswerAttempt)
class AnswerAttemptAdmin(admin.ModelAdmin):
    list_display = ("session", "attempt_number", "student", "hints_before", "is_independent", "created_at")
    list_filter = ("is_independent",)


@admin.register(VerificationResult)
class VerificationResultAdmin(admin.ModelAdmin):
    list_display = ("attempt", "method", "verdict", "confidence", "provider", "created_at")
    list_filter = ("method", "verdict")


@admin.register(LearningProgress)
class LearningProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "topic",
        "status",
        "attempts_count",
        "correct_count",
        "hints_count",
        "last_activity_at",
    )
    list_filter = ("status",)
    autocomplete_fields = ("topic",)


@admin.register(KnowledgeMapNode)
class KnowledgeMapNodeAdmin(admin.ModelAdmin):
    list_display = ("route_key", "order", "topic", "subject", "grade", "x", "y")
    list_filter = ("route_key",)
    autocomplete_fields = ("topic", "subject")
