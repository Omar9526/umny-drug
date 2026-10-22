from django.contrib import admin

from .models import ParentNotification


@admin.register(ParentNotification)
class ParentNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "parent", "student", "kind", "created_at", "read_at")
    list_filter = ("kind",)
    search_fields = ("title",)
