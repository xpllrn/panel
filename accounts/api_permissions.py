from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Allow access only to admin/staff users."""

    def has_permission(self, request, view):
        return (
            request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_admin_role())
        )


class IsMember(BasePermission):
    """Allow access only to member (non-admin) users."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return not request.user.is_staff and not request.user.is_admin_role()


class IsAdminOrReadOnlyMember(BasePermission):
    """Admin gets full access, members get read-only."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_admin_role():
            return True
        # Members can only read
        return request.method in ("GET", "HEAD", "OPTIONS")
