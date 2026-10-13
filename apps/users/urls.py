from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from .views import (
    SignupAPIView,
    LogoutAPIView, 
    EmployerDashboardAPIView,
    CandidateDashboardAPIView,
    CandidateProfileDetailAPIView,
    EmployerProfileDetailAPIView,
    EmployerListAPIView,
)
from .admin_views import (
    AdminPlatformStatsAPIView,
    AdminVerifyEmployerAPIView,
    AdminModerateUserAPIView,
    AdminModerateJobAPIView,
    AdminAuditLogAPIView
)


urlpatterns = [
    path('auth/signup/', SignupAPIView.as_view(), name='signup'),
    path('auth/logout/', LogoutAPIView.as_view(), name='logout'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('dashboard/employer/', EmployerDashboardAPIView.as_view(), name='employer_dashboard'),
    path('dashboard/candidate/', CandidateDashboardAPIView.as_view(), name='candidate_dashboard'),

    path('profile/employer/<int:pk>/', EmployerProfileDetailAPIView.as_view(), name="employer_profile_detail"), 
    path('profile/candidate/<int:pk>/', CandidateProfileDetailAPIView.as_view(), name="candidate_profile_detail"),

    path('api/admin/stats/', AdminPlatformStatsAPIView.as_view(), name="admin_stats"),
    path('api/admin/employer/<int:profile_id>/verify/', AdminVerifyEmployerAPIView.as_view(), name="admin_verify_employer"),
    path('api/admin/users/<int:user_id>/block/', AdminModerateUserAPIView.as_view(), name="admin_block_user"),
    path('api/admin/jobs/<int:job_id>/remove/', AdminModerateJobAPIView.as_view(), name="admin_remove_job"),
    path('api/admin/audit-logs/', AdminAuditLogAPIView.as_view(), name='admin_audit_logs'),
    


    path('employers/', EmployerListAPIView.as_view(), name="employer"),
]

