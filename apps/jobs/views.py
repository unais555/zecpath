from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from apps.users.permissions import IsEmployer
from .models import Job
from .serializers import JobSerializer
from .permissions import IsJobOwner

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