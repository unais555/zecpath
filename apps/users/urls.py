from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView
from .views import (
    SignupAPIView,
    LogoutAPIView, 
    EmployerDashboardAPIView,
    CandidateDashboardAPIView,
    CandidateProfileDetailAPIView,
    EmployerProfileDetailAPIView,
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
]

