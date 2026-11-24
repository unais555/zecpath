import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.jobs.models import (
    AIAnswer,
    AICallLog,
    AIInterviewSession,
    AIQuestion,
    Application,
    Job,
)
from apps.jobs.tasks import execute_external_call
from apps.users.models import CandidateProfile, EmployerProfile

User = get_user_model()


class InterviewWorkflowIntegrationTests(APITestCase):
    """
    Integration Tests for the AI Interview Workflow:
    Validates outbound call task execution, answer submission API,
    and endpoint authentication guards.
    """

    def setUp(self):
        cache.clear()

        self.employer_user = User.objects.create_user(
            email="int_employer@zecpath.com",
            password="StrongPassword123!",
            role=User.Role.EMPLOYER,
        )
        self.candidate_user = User.objects.create_user(
            email="int_candidate@zecpath.com",
            password="StrongPassword123!",
            role=User.Role.CANDIDATE,
        )

        self.employer_profile = EmployerProfile.objects.get(user=self.employer_user)
        self.candidate_profile = CandidateProfile.objects.get(user=self.candidate_user)
        self.candidate_token = str(RefreshToken.for_user(self.candidate_user).access_token)

        self.job = Job.objects.create(
            employer=self.employer_profile,
            title="Backend Django Developer",
            description="API and microservices development",
            skills="Python, Django, REST",
            experience=2,
            location="Remote",
            status="open",
            is_automation_enabled=True,
        )

        TemplateModel = Job.screening_templates.field.model
        self.template_1 = TemplateModel.objects.create(
            job=self.job,
            base_question="How does Django middleware process requests and responses?",
            order=0,
            requires_follow_up=False,
        )

        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate_profile,
            ats_score=88.0,
        )
        self.session = AIInterviewSession.objects.create(
            application=self.application,
            current_question_index=0,
        )
        self.question = AIQuestion.objects.create(
            session=self.session,
            question_text=self.template_1.base_question,
            order=0,
        )
        self.call_log = AICallLog.objects.create(
            application=self.application,
            status=AICallLog.CallStatus.QUEUED,
        )

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @patch("apps.jobs.services.ai_voice_bridge.Client")
    def test_execute_external_call_triggers_twilio_and_saves_sid(self, mock_twilio_client):
        """Validates execute_external_call sets IN_PROGRESS and stores Twilio Call SID."""
        mock_call = MagicMock()
        mock_call.sid = "CA_mock_sid_98765"
        mock_twilio_client.return_value.calls.create.return_value = mock_call

        phone = getattr(self.candidate_profile.user, "phone_number", None) or "+919876543210"
        setattr(self.candidate_profile, "phone_number", phone)
        self.candidate_profile.save()

        result = execute_external_call.apply(args=[self.call_log.id]).get()

        self.call_log.refresh_from_db()
        self.assertIn("CA_mock_sid_98765", result)
        self.assertEqual(self.call_log.provider_call_sid, "CA_mock_sid_98765")
        self.assertEqual(self.call_log.status, AICallLog.CallStatus.IN_PROGRESS)

    @patch("apps.jobs.services.scoring_engine.openai.chat.completions.create")
    def test_submit_answer_api_evaluates_and_saves_score(self, mock_openai):
        """Validates POST /interviews/questions/{id}/submit-answer/ end-to-end."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "relevance": 92,
                "completeness": 88,
                "feedback": "Accurate explanation of Django request/response hooks.",
            }
        )
        mock_openai.return_value = mock_response

        response = self.client.post(
            f"/interviews/questions/{self.question.id}/submit-answer/",
            data={
                "answer_text": (
                    "Middleware wraps views in layers, running process_request "
                    "on the way in and process_response on the way out."
                )
            },
            format="json",
            **self._auth_header(self.candidate_token),
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_201_CREATED],
            msg=f"Unexpected status {response.status_code}: {response.data}",
        )
        saved_answer = AIAnswer.objects.filter(question=self.question).first()
        self.assertIsNotNone(saved_answer)
        self.assertEqual(saved_answer.relevance_score, 92)

    def test_unauthenticated_cannot_submit_interview_answer(self):
        """Security Check: unauthenticated requests to submit-answer are rejected."""
        response = self.client.post(
            f"/interviews/questions/{self.question.id}/submit-answer/",
            data={"answer_text": "Unauthorized answer attempt."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)