from rest_framework.permissions import BasePermission

class IsEmployer(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == request.user.Role.EMPLOYER
        )

class IsCandidate(BasePermission):
    def has_permission(self, request, view):
            return bool(
                request.user and
                request.user.is_authenticated and
                request.user.role == request.user.Role.CANDIDATE
            )

class IsAdmin(BasePermission):
     def has_permission(self, request, view):
          return bool(
               request.user and
               request.user.is_authenticated and
               (request.user.role == request.user.Role.ADMIN or request.user.is_superuser)
          )

class IsOwnerOrAdmin(BasePermission):
     def has_object_permission(self, request, view, obj):
          if request.user.role == request.user.Role.ADMIN or request.user.is_superuser:
               return True
          return obj.user == request.user