from django.shortcuts import render, get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import generics, status, views
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.throttling import UserRateThrottle

from apps.users.permissions import IsEmployer, IsCandidate
from .models import ( Job, 
    Application, 
    ApplicationLog, 
    SavedJob, 
    AIAnswer, 
    AIQuestion, 
    AICallLog, 
    AIInterviewSession,
    InterviewReminderLog,
    InterviewSchedule,
    ) 
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
from .services.scoring_engine import AnswerScoringEngine
from .services.report_generator import CandidateReportService
from .tasks import send_async_email
from .services.analytics import AnalyticsService
import logging
from apps.jobs.models import AuditLog


security_logger = logging.getLogger('zecpath.security')

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


class SubmitAnswerAPIView(views.APIView):
    """API to submit a candidate's answer and instantly generate a score."""
    
    def post(self, request, question_id):
        question = get_object_or_404(AIQuestion, id=question_id)
        
        # 1. Store Raw Answer
        answer_text = request.data.get('answer_text')
        confidence = request.data.get('confidence_indicator', 1.0)
        
        if not answer_text:
            return Response({"error": "answer_text is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        answer = AIAnswer.objects.create(
            question=question,
            answer_text=answer_text,
            confidence_indicator=confidence
        )
        
        # 2. Trigger Scoring Engine
        scored_answer = AnswerScoringEngine.evaluate_and_score(answer)
        
        return Response({
            "message": "Answer submitted and scored successfully.",
            "final_score": scored_answer.final_score,
            "feedback": scored_answer.feedback
        }, status=status.HTTP_201_CREATED)


class RetrieveInterviewResultsAPIView(views.APIView):
    """API for the Employer to retrieve the total scores for an interview."""
    
    def get(self, request, session_id):
        session = get_object_or_404(AIInterviewSession, id=session_id)
        answers = AIAnswer.objects.filter(question__session=session)
        
        if not answers.exists():
            return Response({"message": "No answers recorded yet."}, status=status.HTTP_200_OK)
            
        # Calculate overall interview average
        total_score = sum(ans.final_score for ans in answers if ans.final_score)
        average_score = round(total_score / answers.count(), 2)
        
        results = [
            {
                "question": ans.question.question_text,
                "answer": ans.answer_text,
                "score": ans.final_score,
                "feedback": ans.feedback
            } for ans in answers
        ]
        
        return Response({
            "session_id": session.id,
            "overall_score": average_score,
            "detailed_results": results
        }, status=status.HTTP_200_OK)




class InterviewReminderAPIView(views.APIView):
    """API for viewing reminder history and manually triggering ad-hoc reminders."""
    
    def get(self, request, schedule_id):
        """Fetch the history of reminders sent for a specific interview."""
        schedule = get_object_or_404(InterviewSchedule, id=schedule_id)
        
        # Fetch all reminder logs for this schedule
        reminders = schedule.reminders.all().values(
            'reminder_type', 'status', 'sent_at', 'error_message'
        )
        
        return Response({
            "schedule_id": schedule.id,
            "candidate": schedule.application.candidate.user.email,
            "scheduled_time": schedule.slot.start_time,
            "reminders_history": list(reminders)
        }, status=status.HTTP_200_OK)

    def post(self, request, schedule_id):
        """Manually trigger an ad-hoc reminder to the candidate."""
        schedule = get_object_or_404(InterviewSchedule, id=schedule_id)
        
        candidate_email = schedule.application.candidate.user.email
        job_title = schedule.application.job.title
        
        context = {
            'candidate_email': candidate_email,
            'job_title': job_title,
            'start_time': schedule.slot.start_time.strftime('%A, %B %d at %I:%M %p'),
            'reminder_type': 'MANUAL'
        }
        
        try:
            # 1. Dispatch the Celery task instantly
            send_async_email.delay(
                recipient_email=candidate_email,
                subject=f"Important Reminder: Interview for {job_title}",
                template_name='interview_reminder',
                context=context,
                event_type='REMINDER_MANUAL'
            )
            
            # 2. Log the manual action
            InterviewReminderLog.objects.create(
                schedule=schedule,
                reminder_type=InterviewReminderLog.ReminderType.MANUAL,
                status=InterviewReminderLog.Status.SENT
            )
            
            return Response(
                {"message": "Manual reminder queued successfully."}, 
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {"error": f"Failed to trigger reminder: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AIReportThrottle(UserRateThrottle):
    scope = 'ai_report'

    

class CandidateReportAPIView(views.APIView):
    """Generates and retrieves the AI Candidate Report for Employers."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [AIReportThrottle]

    def get(self, request, application_id):
        application = get_object_or_404(Application, id=application_id)
        
        # 1. Strict Access Control: Only the Employer who posted the job can view it
        if request.user.role != getattr(request.user.Role, 'EMPLOYER', 'EMPLOYER'):
            return Response({"error": "Unauthorized. Employer access required."}, status=status.HTTP_403_FORBIDDEN)
            
        if application.job.employer.user != request.user:
            return Response({"error": "Unauthorized. You do not own this job posting."}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            # 2. Trigger the Engine
            report = CandidateReportService.generate_report(application_id)
            
            # 3. Return Structured Report Format (JSON)
            return Response({
                "application_id": application.id,
                "candidate": application.candidate.user.email,
                "job_title": application.job.title,
                "metrics": {
                    "ats_score": getattr(application, 'ats_score', 0),
                    "ai_interview_score": round((float(report.overall_score) - (float(getattr(application, 'ats_score', 0)) * 0.3)) / 0.7, 2) if report.overall_score else 0,
                    "overall_combined_score": report.overall_score
                },
                "insights": {
                    "summary": report.summary,
                    "strengths": report.strengths,
                    "risks": report.risks
                },
                "generated_at": report.generated_at
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




class JobAnalyticsAPIView(APIView):
    """Provides hiring funnel metrics and conversion rates for a specific job."""
    permission_classes = [IsAuthenticated, IsEmployer]

    def get(self, request, job_id):
        # Access Control: Only Employers
        if request.user.role != getattr(request.user.Role, 'EMPLOYER', 'EMPLOYER'):
            # 1. Write to security.log file
            security_logger.warning(
                f"Unauthorized access attempt by {request.user.email} (Role: {request.user.role}) on Analytics for Job {job_id}"
            )
            # 2. Save immutable record to DB Audit Trail
            AuditLog.objects.create(
                user=request.user,
                action='UNAUTHORIZED_ANALYTICS_ACCESS_ATTEMPT',
                target_object_id=str(job_id),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return Response({"error": "Only employers can view analytics."}, status=status.HTTP_403_FORBIDDEN)
            
        # Verify the employer actually owns this job before showing data
        from .models import Job
        if not Job.objects.filter(id=job_id, employer__user=request.user).exists():
             return Response({"error": "Job not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        try:
            data = AnalyticsService.get_job_funnel_metrics(job_id, request.user.id)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)