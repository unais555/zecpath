from rest_framework.permissions import BasePermission

class IsJobOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.employer == request.user.employer_profile

class IsEmployerForApplication(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.job.employer.user == request.user