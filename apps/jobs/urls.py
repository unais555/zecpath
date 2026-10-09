from django.urls import path
from .views import (
    EmployerJobDetailAPIView,
    EmployerJobListCreateAPIView,
    PublicJobListAPIView,
    ApplyJobAPIView,
    CandidateApplicationHistoryAPIView,
    EmployerApplicationStatusAPIView,
    EmployerAnalyticsAPIView,
    EmployerApplicantListAPIView
)

urlpatterns = [
    path('employer/jobs/', EmployerJobListCreateAPIView.as_view(), name="employer_jobs"),
    path('employer/jobs/<int:pk>/', EmployerJobDetailAPIView.as_view(), name="employer_job_detail"),
    path('jobs/', PublicJobListAPIView.as_view(), name='public_job_list'),
    path('jobs/<int:job_id>/apply/', ApplyJobAPIView.as_view(), name='apply_job'),
    path('candidate/applications/', CandidateApplicationHistoryAPIView.as_view(), name='candidate_applications'),
    path('employer/applications/<int:pk>/status/', EmployerApplicationStatusAPIView.as_view(), name='employer_update_status'),
    path('employer/applicants/', EmployerApplicantListAPIView.as_view(), name='employer_applicants'),
    path('employer/analytics/', EmployerAnalyticsAPIView.as_view(), name='employer_analytics'),
]
