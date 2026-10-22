from django.contrib import admin

from .models import Curriculum, Grade, Section, Subject, Topic


class GradeInline(admin.TabularInline):
    model = Grade
    extra = 0


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ("code", "name_ru", "country", "is_active")
    inlines = (GradeInline,)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("number", "curriculum", "name_ru", "stage")
    list_filter = ("curriculum",)
    search_fields = ("name_ru",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "name_ru",
        "slug",
        "curriculum",
        "strategy",
        "grade_from",
        "grade_to",
        "order",
        "is_active",
    )
    list_filter = ("curriculum", "strategy", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name_ru", "name_ky", "slug")
    prepopulated_fields = {"slug": ("name_ru",)}


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0
    fields = ("order", "slug", "name_ru", "name_ky", "difficulty", "is_active")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "subject", "grade", "order")
    list_filter = ("subject", "grade__number")
    search_fields = ("name_ru", "name_ky")
    inlines = (TopicInline,)
    autocomplete_fields = ("subject",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "section", "difficulty", "order", "is_active")
    list_filter = ("section__subject", "section__grade__number", "difficulty", "is_active")
    search_fields = ("name_ru", "name_ky", "slug", "keywords")
    autocomplete_fields = ("section",)
