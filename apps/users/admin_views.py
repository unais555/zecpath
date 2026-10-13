from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404

from .models import EmployerProfile, CandidateProfile, AdminActionLog
from apps.jobs.models import Job, Application

User = get_user_model()

def log_admin_action(admin_user, action, target):
    AdminActionLog.objects.create(admin=admin_user, action=action, target_object=target)

class AdminPlatformStatsAPIView(APIView):
    permission_classes = [IsAdminUser]


    def get(self, request):
        metrics = {
            "users" : {
                "total" : User.objects.count(),
                "employers" : EmployerProfile.objects.count(),
                "candidates" : CandidateProfile.objects.count()
            },
            "jobs" : {
                "total_posted" : Job.objects.count(),
                "currently_active" : Job.objects.filter(is_active=True).count(),
                "spam_removed" : Job.objects.filter(status=Job.JobStatus.CLOSED, is_active=False).count()
            },
            "applications" : {
                "total_applications" : Application.objects.count(),
                "hired_candidates" : Application.objects.filter(status=Application.ApplicationStatus.SELECTED).count()
            }
        }
        return Response({"success": True, "metrices": metrics})


class AdminVerifyEmployerAPIView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, profile_id):
        employer = get_object_or_404(EmployerProfile, id=profile_id)
        employer.is_verified = True
        employer.save(update_fields=['is_verified'])

        log_admin_action(request.user, "Verified Employer", f"Company: {employer.company_name}")
        return Response({"message": f"{employer.company_name} has been successfully verified."})
        

class AdminModerateUserAPIView(APIView):
    permission_classes = [IsAdminUser]


    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.is_active = False
        user.save(update_fields=['is_active'])

        log_admin_action(request.user, "Blocked user", f"User {user.email}")
        return Response({"success": True, "message": f"User {user.email} has been blocked and disabled."})

    
class AdminModerateJobAPIView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, job_id):
        job = get_object_or_404(Job, id=job_id)
        job.is_active = False
        job.status = Job.JobStatus.CLOSED
        job.save(update_fields=['is_active', 'status'])

        log_admin_action(request.user, "Removed Spam Jobs", f"Job: {job.title} by {job.employer.company_name}")
        return Response({"message": f"Job '{job.title}' has been successfully removed from the platform."})



class AdminAuditLogAPIView(APIView):
    
    permission_classes = [IsAdminUser]

    def get(self, request):
        logs = AdminActionLog.objects.select_related('admin').order_by('-timestamp')[:50]
        data = [
            {
                "admin": log.admin.email,
                "action": log.action,
                "target": log.target_object,
                "timestamp": log.timestamp
            }
            for log in logs
        ]
        return Response({"audit_trail": data})