from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import CandidateProfile, EmployerProfile
from .nlp_engine import build_resume_json_schema
from .permissions import IsCandidate, IsEmployer, IsOwnerOrAdmin
from .resume_parser import process_resume_file
from .serializers import (
    CandidateProfileSerializer,
    EmployerProfileSerializer,
    ResumeUploadSerializer,
    UserRegistrationSerializers,
)
from .services import deactivate_user_account


class SignupAPIView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializers
    permission_classes = [AllowAny]


# We inherit from the predefined view to safely customize it
class ThrottledLoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        request={
            "application/json": {
                "type": "object",
                "properties": {"refresh": {"type": "string"}},
            }
        },
        responses={205: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Successfully logged out."},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except Exception:
            return Response(
                {"error": "Invalid or missing refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class EmployerDashboardAPIView(APIView):
    permission_classes = [IsEmployer]

    @extend_schema(tags=["Users"], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        profile = request.user.employer_profile
        return Response(
            {
                "message": "Welcome to the Employer Dashboard!",
                "company_name": profile.company_name,
                "email": request.user.email,
            }
        )


class CandidateDashboardAPIView(APIView):
    permission_classes = [IsCandidate]

    @extend_schema(tags=["Users"], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        profile = request.user.candidate_profile
        return Response(
            {
                "message": "Welcome to the Candidate Dashboard!",
                "skills": profile.skills,
                "email": request.user.email,
            }
        )


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
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = ["size", "is_verified", "domain"]
    search_fields = ["company_name", "domain"]
    ordering_fields = ["company_name"]

    def get_queryset(self):
        return EmployerProfile.objects.select_related("user").all()


class ResumeParseAndUploadAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCandidate]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Users"],
        request=ResumeUploadSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = ResumeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # uploaded_file = serializer.data["resume"]
        uploaded_file = request.FILES.get("resume")

        if not uploaded_file:
            return Response(
                {"error": "No resume file was found in the request."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            parsed_data = process_resume_file(uploaded_file)
            uploaded_file.seek(0)  # Rewind file pointer so S3 doesn't upload an empty 0-byte file

            cleaned_text = parsed_data["cleaned_text"]
            structured_resume_data = build_resume_json_schema(cleaned_text)

            profile = request.user.candidate_profile
            profile.resume = uploaded_file
            profile.parsed_resume_text = cleaned_text
            profile.resume_parsed_at = timezone.now()
            profile.structured_resume_data = structured_resume_data
            profile.save(
                update_fields=[
                    "resume",
                    "parsed_resume_text",
                    "structured_resume_data",
                    "resume_parsed_at",
                ]
            )

            return Response(
                {
                    "success": True,
                    "message": "Resume uploaded and parsed successfully.",
                    "resume_url": profile.resume.url,  # Temporary signed cloud URL
                    "metadata": {
                        "filename": parsed_data["filename"],
                        "format": parsed_data["extension"],
                        "word_count": parsed_data["word_count"],
                        "character_count": parsed_data["character_count"],
                        "parsed_at": profile.resume_parsed_at,
                    },
                    "structured_data": structured_resume_data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
