from django.contrib import admin

from .models import ParentNotification, PushSubscription


@admin.register(ParentNotification)
class ParentNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "parent", "student", "kind", "created_at", "read_at")
    list_filter = ("kind",)
    search_fields = ("title",)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    """Device list for support; endpoint and encryption keys are deliberately not shown."""

    list_display = ("parent", "user_agent", "failures", "last_sent_at", "created_at")
    fields = ("parent", "user_agent", "failures", "last_sent_at", "created_at")
    readonly_fields = fields
    search_fields = ("parent__user__email",)

    def has_add_permission(self, request) -> bool:
        return False
