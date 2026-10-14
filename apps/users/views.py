from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone

from .serializers import (
    UserRegistrationSerializers, 
    CandidateProfileSerializer, 
    EmployerProfileSerializer,
    ResumeUploadSerializer,
)
from .permissions import IsCandidate, IsEmployer, IsOwnerOrAdmin
from .models import EmployerProfile, CandidateProfile
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .services import deactivate_user_account
from .resume_parser import process_resume_file


class SignupAPIView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializers
    permission_classes = [AllowAny]

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Invalid or missing refresh token."}, status=status.HTTP_400_BAD_REQUEST)

class EmployerDashboardAPIView(APIView):
    permission_classes = [IsEmployer]

    def get(self, request):
        profile = request.user.employer_profile
        return Response({
            "message": "Welcome to the Employer Dashboard!",
            "company_name": profile.company_name,
            "email": request.user.email
        })


class CandidateDashboardAPIView(APIView):
    permission_classes = [IsCandidate]

    def get(self, request):
        profile = request.user.candidate_profile
        return Response({
            "message": "Welcome to the Candidate Dashboard!",
            "skills": profile.skills,
            "email": request.user.email
        })
class EmployerProfileDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EmployerProfile.objects.all()
    serializer_class = EmployerProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def perform_destroy(self, instance):
        deactivate_user_account(instance.user)
        

class CandidateProfileDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CandidateProfile.objects.all()
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def perform_destroy(self, instance):
        deactivate_user_account(instance.user)

class EmployerListAPIView(generics.ListAPIView):
    queryset = EmployerProfile.objects.get_queryset()
    serializer_class = EmployerProfileSerializer
    permission_classes = [AllowAny]
    filter_backends = [ DjangoFilterBackend, SearchFilter, OrderingFilter ]

    filterset_fields = ['size', 'is_verified', 'domain']
    search_fields = ['company_name', 'domain']
    ordering_fields = ['company_name']

    def get_queryset(self):
        return EmployerProfile.objects.select_related('user').all()

class ResumeParseAndUploadAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCandidate]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        print("FILES RECEIVED:", request.FILES)
        print("DATA RECEIVED:", request.data)
        serializer = ResumeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # uploaded_file = serializer.data["resume"]
        uploaded_file = request.FILES.get('resume')

        parsed_data = process_resume_file(uploaded_file)

        profile = request.user.candidate_profile
        profile.resume = uploaded_file
        profile.parsed_resume_text = parsed_data["cleaned_text"]
        profile.resume_parsed_at = timezone.now()
        profile.save(update_fields=['resume', 'parsed_resume_text', 'resume_parsed_at'])

        
        return Response({
            "success": True,
            "message": "Resume uploaded and parsed successfully.",
            "metadata": {
                "filename": parsed_data["filename"],
                "format": parsed_data["extension"],
                "word_count": parsed_data["word_count"],
                "character_count": parsed_data["character_count"],
                "parsed_at": profile.resume_parsed_at
            },
            "cleaned_text": parsed_data["cleaned_text"]
        }, status=status.HTTP_200_OK)
        # return Response({"success":True})



