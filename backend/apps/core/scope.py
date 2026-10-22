"""Who is the data about: the calling student, or (for a parent) one of their children.

Shared by curriculum, learning and quizzes views so the ``?student=`` convention behaves the same
everywhere: a parent may only pass an active child of their own family; anyone else gets their own
profile (or ``None`` for accounts without one).
"""

from __future__ import annotations

from apps.accounts.models import StudentProfile


def request_lang(request) -> str:
    lang = request.query_params.get("lang") or getattr(request.user, "preferred_language", "ru")
    return lang if lang in ("ru", "ky") else "ru"


def student_in_scope(request) -> StudentProfile | None:
    user = request.user
    own = getattr(user, "student_profile", None)
    student_id = request.query_params.get("student")
    if student_id and getattr(user, "is_parent", False):
        return (
            StudentProfile.objects.filter(id=student_id, family_id=user.family_id, is_active=True)
            .select_related("grade__curriculum", "user")
            .first()
        )
    return own
