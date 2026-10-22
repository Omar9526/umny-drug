from django.contrib import admin

from .models import AIConversation, AIMessage, AIUsage, LearningSession, SolutionStep


class AIMessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0
    fields = ("created_at", "role", "command", "content", "flagged", "flag_reason", "latency_ms")
    readonly_fields = fields
    can_delete = False


@admin.register(LearningSession)
class LearningSessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "student",
        "subject",
        "mode",
        "status",
        "outcome",
        "hints_used",
        "last_activity_at",
    )
    list_filter = ("status", "mode", "outcome", "subject")
    search_fields = ("title",)
    readonly_fields = (
        "hints_used",
        "explanations_count",
        "attempts_count",
        "correct_attempts",
        "solution_revealed",
    )


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("session", "provider", "model", "demo_mode", "input_tokens", "output_tokens", "cost_usd")
    list_filter = ("provider", "demo_mode")
    inlines = (AIMessageInline,)


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    """Quality queue: messages a child flagged as wrong."""

    list_display = ("created_at", "conversation", "role", "command", "flagged", "flag_reason")
    list_filter = ("flagged", "role", "command")
    search_fields = ("content",)
    readonly_fields = ("conversation", "role", "command", "content", "payload", "created_at")


@admin.register(SolutionStep)
class SolutionStepAdmin(admin.ModelAdmin):
    list_display = ("session", "order", "title", "is_hint", "revealed_at")


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    """Cost monitoring: filter by day/purpose, sum cost_usd."""

    list_display = (
        "created_at",
        "purpose",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "latency_ms",
        "family",
    )
    list_filter = ("purpose", "provider", "model")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AIUsage._meta.fields]

    def has_add_permission(self, request):
        return False
