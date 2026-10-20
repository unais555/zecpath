from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.users.models import CandidateProfile, EmployerProfile
from .models import Job, Application
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

class JobFlowIntegrationTests(APITestCase):
    def setUp(self):
        # Create an Employer
        self.employer_user = User.objects.create_user(email='employer@test.com', password='password123', role='EMPLOYER')
        self.employer_profile = EmployerProfile.objects.create(user=self.employer_user, company_name="TechCorp")
        
        # Create a Candidate
        self.candidate_user = User.objects.create_user(
            email='candidate@test.com', 
            password='password123'
        )

        self.candidate_user.role = User.Role.CANDIDATE 
        self.candidate_user.save()

        dummy_resume = SimpleUploadedFile(
            "test_resume.pdf", 
            b"dummy resume content", 
            content_type="application/pdf"
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            resume=dummy_resume
        )

        

        # Create a Job
        self.job = Job.objects.create(
            employer=self.employer_profile,
            title="Backend Engineer",
            description="We are looking for a backend engineer.",
            skills="Python, Django, PostgreSQL",
            experience=3,
            location="Remote",
            is_automation_enabled=True,
            status=Job.JobStatus.OPEN
        )
        self.apply_url = f'/jobs/{self.job.id}/apply/'

    def test_auth_access_leak(self):
        """Security Audit: Unauthenticated users should be blocked from applying."""
        response = self.client.post(self.apply_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_successful_job_application_flow(self):
        """Integration Test: Candidate can apply and default status is PENDING."""
        self.client.force_authenticate(user=self.candidate_user)
        
        # Create a dummy PDF file for the test
        dummy_resume = SimpleUploadedFile(
            "test_resume.pdf", 
            b"dummy resume content", 
            content_type="application/pdf"
        )
        
        # Pass the required data in the POST request
        response = self.client.post(
            self.apply_url, 
            data={'resume': dummy_resume}, # Add any other required fields here
            format='multipart' # Required for file uploads
        )
        
        if response.status_code != 201:
            print(f"\nDEBUG - 400 Error Reason: {response.data}\n")
            
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Application.objects.count(), 1)