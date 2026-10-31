import json
from unittest.mock import patch
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.jobs.models import AIInterviewSession, AIQuestion, Application, Job, EmployerProfile, CandidateProfile
from django.urls import reverse


User = get_user_model()

class ScoringAPITests(APITestCase):
    def setUp(self):
        # 1. Create dummy users (Signals will auto-create their empty profiles)
        self.employer_user = User.objects.create_user(email='emp@test.com', password='pwd', role=User.Role.EMPLOYER)
        
        # THE FIX: Fetch the auto-created profile and update it, instead of creating a duplicate
        self.employer_profile = EmployerProfile.objects.get(user=self.employer_user)
        self.employer_profile.company_name = "Tech Corp"
        self.employer_profile.save()
        
        self.candidate_user = User.objects.create_user(email='cand@test.com', password='pwd', role=User.Role.CANDIDATE)
        self.candidate_profile = CandidateProfile.objects.get(user=self.candidate_user)

        # 2. Create Job and Application
        self.job = Job.objects.create(
            employer=self.employer_profile, 
            title="Backend Dev", 
            description="Django dev", 
            skills="Django, Python", 
            experience=2, 
            location="Remote", 
            # THE FIX: Use lowercase 'open' (or check your models.py for the exact casing)
            status='open' 
        )

        self.application = Application.objects.create(
            job=self.job, candidate=self.candidate_profile, status='PENDING'
        )

        # 3. Create AI Session and Question
        self.session = AIInterviewSession.objects.create(application=self.application)
        self.question = AIQuestion.objects.create(
            session=self.session, 
            question_text="How do you handle background tasks in Django?", 
            order=1
        )
        
        self.submit_url = reverse('submit-answer', kwargs={'question_id': self.question.id})
        self.results_url = reverse('interview-results', kwargs={'session_id': self.session.id})
        
    # THE MAGIC: @patch intercepts the call to OpenAI and returns our fake data
    @patch('apps.jobs.services.scoring_engine.openai.chat.completions.create')
    def test_submit_answer_and_score(self, mock_openai):
        # 1. Setup the fake OpenAI JSON response
        class MockMessage:
            content = json.dumps({
                "relevance": 90,
                "completeness": 80,
                "feedback": "Great mention of Celery."
            })
        class MockChoice:
            message = MockMessage()
        
        mock_openai.return_value.choices = [MockChoice()]

        # 2. Send the POST request
        payload = {
            "answer_text": "I use Celery and Redis to handle async background tasks.",
            "confidence_indicator": 0.98
        }
        response = self.client.post(self.submit_url, data=payload, format='json')

        # 3. Verify the API Response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Math Check: (90 * 0.4) + (80 * 0.6) = 36 + 48 = 84.0
        self.assertEqual(float(response.data['final_score']), 84.0)
        self.assertEqual(response.data['feedback'], "Great mention of Celery.")

    @patch('apps.jobs.services.scoring_engine.openai.chat.completions.create')
    def test_retrieve_interview_results(self, mock_openai):
        # Setup mock and submit an answer first
        class MockMessage:
            content = json.dumps({"relevance": 100, "completeness": 100, "feedback": "Perfect."})
        class MockChoice:
            message = MockMessage()
        mock_openai.return_value.choices = [MockChoice()]
        
        self.client.post(self.submit_url, {"answer_text": "Perfect answer"}, format='json')

        # Test the GET Results endpoint
        response = self.client.get(self.results_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['overall_score']), 100.0)
        self.assertEqual(len(response.data['detailed_results']), 1)