from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import ConsentRecord, Family, ParentProfile, ParentStudentLink, StudentProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("-date_joined",)
    list_display = ("display_name", "email", "role", "family", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("display_name", "email")
    readonly_fields = ("date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Профиль", {"fields": ("display_name", "role", "preferred_language", "family", "phone")}),
        ("Права", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Даты", {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "display_name", "role", "password1", "password2")}),
    )


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "display_code", "created_at", "code_rotated_at")
    search_fields = ("name", "code")
    readonly_fields = ("code", "code_rotated_at", "created_by")


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "family", "country", "notify_weekly_report")
    search_fields = ("user__display_name", "user__email")
    autocomplete_fields = ("user", "family")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("nickname", "grade", "family", "language", "is_active", "created_at")
    list_filter = ("grade__number", "language", "is_active")
    search_fields = ("nickname", "family__code")
    autocomplete_fields = ("user", "family")
    exclude = ("pin_hash",)
    readonly_fields = ("pin_failed_attempts", "pin_locked_until", "deleted_at")


@admin.register(ParentStudentLink)
class ParentStudentLinkAdmin(admin.ModelAdmin):
    list_display = ("parent", "student", "relation", "is_primary")
    autocomplete_fields = ("parent", "student")


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("granted_by", "student", "consent_type", "version", "granted", "granted_at", "revoked_at")
    list_filter = ("consent_type", "granted")
    readonly_fields = [f.name for f in ConsentRecord._meta.fields]

    def has_add_permission(self, request):
        return False
