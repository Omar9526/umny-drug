"""Role and family-scope permissions.

Rule of thumb: role permissions gate *which* endpoints a user may call; family scoping
(``FamilyScopedQuerysetMixin``) gates *which rows* they may see. Both are enforced on
the server; the frontend only mirrors them for UX.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsStudent(BasePermission):
    message = "Доступно только ученику."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_student)


class IsParent(BasePermission):
    message = "Доступно только родителю."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_parent)


class IsAdminRole(BasePermission):
    message = "Доступно только администратору."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_role)


class IsStudentOrParent(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and (user.is_student or user.is_parent))


class FamilyScopedQuerysetMixin:
    """Restrict a queryset to the caller's family.

    ``family_lookup`` is the ORM path from the model to its ``Family`` row, e.g.
    ``"student__family"``. Admins see everything; everyone else is filtered.
    """

    family_lookup: str = "family"

    def scope_to_family(self, queryset):
        user = self.request.user
        if user.is_admin_role:
            return queryset
        family_id = user.family_id
        if family_id is None:
            return queryset.none()
        return queryset.filter(**{f"{self.family_lookup}_id": family_id})
