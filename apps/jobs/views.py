from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status

from apps.users.permissions import IsEmployer, IsCandidate
from .models import Job, Application, ApplicationLog
from .serializers import (
    JobSerializer,
    ApplicationSerializer,
    ApplicationStatusUpdateSerializer,
    EmployerApplicantSerializer,
)
from .permissions import IsJobOwner, IsEmployerForApplication
from .filters import JobFilter
from .pagination import JobCursorPagination


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

        resume_url = request.build_absolute_uri(candidate.resume.url)
        application = Application.objects.create(
            job=job,
            candidate=candidate,
            resume_snapshot=resume_url
            )

        serializer = ApplicationSerializer(application)
        return Response({
            "message": "Application submitted successfully!",
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

    def get_queryset(self):
        return Application.objects.filter(
            job__employer=self.request.user.employer_profile
            ).select_related(
            'candidate', 'candidate__user', 'job'
            ).order_by('-applied_at')


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