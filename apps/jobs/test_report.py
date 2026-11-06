import json
from unittest.mock import patch
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.jobs.models import (
    EmployerProfile, CandidateProfile, Job, Application, 
    AIInterviewSession, AIQuestion, AIAnswer
)

User = get_user_model()

class CandidateReportAPITests(APITestCase):
    def setUp(self):
        # 1. Setup Users (Employer who owns the job, Candidate, and a random Employer)
        self.employer_user = User.objects.create_user(email='emp_report@test.com', password='pwd', role=User.Role.EMPLOYER)
        self.employer_profile = EmployerProfile.objects.get(user=self.employer_user)
        
        self.sneaky_employer = User.objects.create_user(email='sneaky@test.com', password='pwd', role=User.Role.EMPLOYER)
        
        self.candidate_user = User.objects.create_user(email='cand_report@test.com', password='pwd', role=User.Role.CANDIDATE)
        self.candidate_profile = CandidateProfile.objects.get(user=self.candidate_user)

        # 2. Create Job & Application
        self.job = Job.objects.create(
            employer=self.employer_profile, title="Backend Dev", 
            description="Django dev", skills="Python", experience=2, status='open', location="Remote"
        )
        self.application = Application.objects.create(
            job=self.job, candidate=self.candidate_profile, status='PENDING'
        )

        # 3. Create Interview Data (Needed to generate the report)
        self.session = AIInterviewSession.objects.create(application=self.application)
        self.question = AIQuestion.objects.create(session=self.session, question_text="What is Django?", order=1)
        self.answer = AIAnswer.objects.create(
            question=self.question, answer_text="A Python web framework.", 
            relevance_score=100, completeness_score=100, final_score=100
        )
        
        self.url = reverse('candidate-report', kwargs={'application_id': self.application.id})

    @patch('apps.jobs.services.report_generator.openai.chat.completions.create')
    def test_generate_report_success(self, mock_openai):
        """Test the employer can successfully generate and view the report."""
        # 1. Mock OpenAI Response
        class MockMessage:
            content = json.dumps({
                "summary": "Excellent candidate.",
                "strengths": ["Django", "Python"],
                "risks": ["Needs more system design experience"]
            })
        class MockChoice:
            message = MockMessage()
        mock_openai.return_value.choices = [MockChoice()]

        # 2. Authenticate as the correct Employer
        self.client.force_authenticate(user=self.employer_user)
        
        # 3. Make the Request
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['insights']['summary'], "Excellent candidate.")
        self.assertEqual(len(response.data['insights']['strengths']), 2)
        # Math check: (0 ATS * 0.3) + (100 Interview * 0.7) = 70.0 overall score
        self.assertEqual(float(response.data['metrics']['overall_combined_score']), 70.0)

    def test_candidate_cannot_view_report(self):
        """Test that a candidate gets a 403 Forbidden error if they try to view their own report."""
        self.client.force_authenticate(user=self.candidate_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_unauthorized_employer_cannot_view(self):
        """Test that Employer B cannot view Employer A's candidate reports."""
        self.client.force_authenticate(user=self.sneaky_employer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)