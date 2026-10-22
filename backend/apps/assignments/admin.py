from django.contrib import admin

from .models import Assignment, AssignmentImage, AssignmentUpload


class AssignmentImageInline(admin.TabularInline):
    model = AssignmentImage
    extra = 0
    readonly_fields = ("mime_type", "width", "height", "size_bytes", "sha256", "expires_at", "purged_at")
    can_delete = False


@admin.register(AssignmentUpload)
class AssignmentUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "source", "status", "provider", "demo_mode", "cost_usd", "created_at")
    list_filter = ("status", "source", "provider", "demo_mode")
    readonly_fields = ("recognition", "input_tokens", "output_tokens", "cost_usd", "processed_at")
    inlines = (AssignmentImageInline,)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "subject", "topic", "grade", "status", "created_at")
    list_filter = ("status", "subject", "grade__number")
    search_fields = ("recognized_text", "confirmed_text")
    autocomplete_fields = ("subject", "topic")
