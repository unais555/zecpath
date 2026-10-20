from django.urls import path
from .views import (
    EmployerJobDetailAPIView,
    EmployerJobListCreateAPIView,
    PublicJobListAPIView,
    ApplyJobAPIView,
    CandidateApplicationHistoryAPIView,
    EmployerApplicationStatusAPIView,
    EmployerAnalyticsAPIView,
    EmployerApplicantListAPIView,
    CandidateApplicationTimelineAPIView,
    CandidateSavedJobsAPIView,
    CandidateJobRecommendationsAPIView,
    EmployerApplicationOverrideAPIView,
)

urlpatterns = [
    path('employer/jobs/', EmployerJobListCreateAPIView.as_view(), name="employer_jobs"),
    path('employer/jobs/<int:pk>/', EmployerJobDetailAPIView.as_view(), name="employer_job_detail"),
    path('jobs/', PublicJobListAPIView.as_view(), name='public_job_list'),
    path('jobs/<int:job_id>/apply/', ApplyJobAPIView.as_view(), name='apply_job'),
    path('candidate/applications/', CandidateApplicationHistoryAPIView.as_view(), name='candidate_applications'),
    path('employer/applications/<int:pk>/status/', EmployerApplicationStatusAPIView.as_view(), name='employer_update_status'),
    path('employer/applicants/<int:job_id>/', EmployerApplicantListAPIView.as_view(), name='employer_applicants'),
    path('employer/analytics/', EmployerAnalyticsAPIView.as_view(), name='employer_analytics'),
    path('candidate/saved-jobs/', CandidateSavedJobsAPIView.as_view(), name='saved_jobs'),
    path('candidate/applications/<int:app_id>/timeline/', CandidateApplicationTimelineAPIView.as_view(), name='application_timeline'),
    path('candidate/recommendations/', CandidateJobRecommendationsAPIView.as_view(), name='job_recommendations'),
    path('applications/<int:pk>/override/', EmployerApplicationOverrideAPIView.as_view(), name='employer-application-override'),
]
