from django.shortcuts import render, get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from apps.users.permissions import IsEmployer, IsCandidate
from .models import Job, Application, ApplicationLog, SavedJob
from .serializers import (
    JobSerializer,
    ApplicationSerializer,
    ApplicationStatusUpdateSerializer,
    EmployerApplicantSerializer,
    ApplicationTimelineSerializer,
    SavedJobSerializer,
)
from .permissions import IsJobOwner, IsEmployerForApplication
from .filters import JobFilter
from .pagination import JobCursorPagination
from .matching_engine import generate_ats_suitability_score


class EmployerJobListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsEmployer]

    def get_queryset(self):
        return Job.objects.filter(employer=self.request.user.employer_profile).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user.employer_profile)

class EmployerJobDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsEmployer, IsJobOwner]

    def get_queryset(self):
        return Job.objects.filter(employer=self.request.user.employer_profile)
        
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.status = Job.JobStatus.CLOSED
        instance.save(update_fields=['is_active', 'status'])

class PublicJobListAPIView(generics.ListAPIView):
    serializer_class = JobSerializer
    permission_classes = [AllowAny]
    pagination_class = JobCursorPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_class = JobFilter
    search_fields = ['title', 'skills', 'employer__company_name']
    ordering_fields = ['created_at', 'min_salary']

    def get_queryset(self):
        return Job.objects.filter(
            status=Job.JobStatus.OPEN, 
            is_active=True
        ).select_related('employer').order_by('-created_at')

    @method_decorator(cache_page(900))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class ApplyJobAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCandidate]

    def post(self, request, job_id):
        job = get_object_or_404(Job, id=job_id)
        candidate = request.user.candidate_profile

        if job.status != Job.JobStatus.OPEN or not job.is_active:
            return Response({"error": "This job is closed and no longer accepting applications."}, status=status.HTTP_400_BAD_REQUEST)

        if Application.objects.filter(job=job, candidate=candidate).exists():
            return Response({"error": "You have already applied for this job."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not candidate.resume:
            return Response({"error": "You must upload a resume to your profile before applying."}, status=status.HTTP_400_BAD_REQUEST)

        suitability_score = generate_ats_suitability_score(candidate, job)

        resume_url = request.build_absolute_uri(candidate.resume.url)
        application = Application.objects.create(
            job=job,
            candidate=candidate,
            resume_snapshot=resume_url,
            ats_score=suitability_score
            )

        serializer = ApplicationSerializer(application)
        return Response({
            "message": "Application submitted successfully!",
            "ats_score": suitability_score,
            "data": serializer.data
        }, status=status.HTTP_201_CREATED)


class CandidateApplicationHistoryAPIView(generics.ListAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, IsCandidate]

    def get_queryset(self):
        return Application.objects.filter(
            candidate=self.request.user.candidate_profile
            ).select_related('job', 'job__employer').order_by('-applied_at')
    

class EmployerApplicationStatusAPIView(generics.UpdateAPIView):
    queryset = Application.objects.all()
    serializer_class = ApplicationStatusUpdateSerializer
    permission_classes = [IsAuthenticated, IsEmployer, IsEmployerForApplication]

    def perform_update(self, serializer):
        application = serializer.instance
        old_status = application.status
        new_status = serializer.validated_data['status']
        notes = serializer.validated_data.pop('notes', '')

        # Update the application status
        application = serializer.save()

        # Create the immutable audit log entry
        ApplicationLog.objects.create(
            application=application,
            updated_by=self.request.user,
            old_status=old_status,
            new_status=new_status,
            notes=notes
        )


class EmployerApplicantListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsEmployer]
    serializer_class = EmployerApplicantSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['status', 'job__id']
    search_fields = ['candidate__skills', 'candidate__user__email']

    def get(self, request, job_id):
        # return Application.objects.filter(
        #     job__employer=self.request.user.employer_profile
        #     ).select_related(
        #     'candidate', 'candidate__user', 'job'
        #     ).order_by('-ats_score')

        job = get_object_or_404(Job, id=job_id, employer=request.user.employer_profile)
        applications = Application.objects.select_related(
            'candidate__user', # Gets the candidate and their underlying User model (first_name, email)
            'job'
        ).filter(job=job).order_by('-ats_score')
        data = []
        for app in applications:
            data.append({
                "application_id": app.id,
                "candidate_name": f"{app.candidate.user.first_name} {app.candidate.user.last_name}",
                "status": app.get_status_display(),
                "suitability_percent": app.ats_score,
                "applied_at": app.applied_at
            })
            
        return Response({
            "job_title": job.title,
            "total_applicants": applications.count(),
            "ranked_candidates": data
        })


class EmployerAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsEmployer]

    def get(self, request):
        employer = request.user.employer_profile
        total_active_jobs = Job.objects.filter(employer=employer, is_active=True).count()
        employer_applications = Application.objects.filter(job__employer=employer)
        total_applications = employer_applications.count()

        shortlisted_count = employer_applications.filter(status=Application.ApplicationStatus.SHORTLISTED).count()
        hired_count = employer_applications.filter(status=Application.ApplicationStatus.SELECTED).count()
        rejected_count = employer_applications.filter(status=Application.ApplicationStatus.REJECTED).count()

        shortlist_ratio = 0
        if total_applications > 0:
            shortlist_ratio = round((shortlisted_count/total_applications)*100, 2)

        return Response({
            "metrics": {
                "active_jobs": total_active_jobs,
                "total_applications": total_applications,
                "pipeline": {
                    "shortlisted": shortlisted_count,
                    "hired": hired_count,
                    "rejected": rejected_count
                },
                "shortlist_ratio_percentage": shortlist_ratio
            }
        })


class CandidateSavedJobsAPIView(generics.ListCreateAPIView):
    serializer_class = SavedJobSerializer
    permission_classes = [IsAuthenticated, IsCandidate]

    def get_queryset(self):
        return SavedJob.objects.filter(
            candidate=self.request.user.candidate_profile
        ).select_related('job', 'job__employer').order_by('-saved_at')

    def perform_create(self, serializer):
        serializer.save(candidate=self.request.user.candidate_profile)


class CandidateApplicationTimelineAPIView(generics.ListAPIView):
    serializer_class = ApplicationTimelineSerializer
    permission_classes = [IsAuthenticated, IsCandidate]

    def get_queryset(self):
        application_id = self.kwargs.get('app_id')
        return ApplicationLog.objects.filter(
            application__id=application_id,
            application__candidate=self.request.user.candidate_profile
        ).order_by('-timestamp')

class CandidateJobRecommendationsAPIView(generics.ListAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsCandidate]

    def get_queryset(self):
        candidate = self.request.user.candidate_profile
        candidate_skills = candidate.skills.split(',') if candidate.skills else []

        if not candidate_skills:
            return Job.objects.none()

        skill_query = Q()
        for skill in candidate_skills:
            skill = skill.strip()
            if skill:
                skill_query |= Q(skills__icontains=skill)
        return Job.objects.filter(
            status=Job.JobStatus.OPEN,
            is_active=True
        ).filter(skill_query).select_related('employer').distinct().order_by('-created_at')[:10]


class EmployerApplicationOverrideAPIView(generics.UpdateAPIView):
    queryset = Application.objects.all()
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        application = self.get_object()

        if application.job.employer != request.user.employer_profile:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        new_status = request.data.get('status')
        new_status_lower = new_status.lower()
        statuses = Application.ApplicationStatus.values
        print(statuses)
        if new_status_lower not in statuses:
            return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)

        application.status = new_status
        application.is_manually_overridden = True
        application.save(update_fields=['status', 'is_manually_overridden'])
        
        return Response({
            "success": True,
            "message": f"Application manually marked as {new_status}.",
            "application_id": application.id
        })