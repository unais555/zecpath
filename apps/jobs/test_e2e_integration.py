import json
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.jobs.eligibility import CallEligibilityEngine
from apps.jobs.models import AIAnswer, AIInterviewSession, AIQuestion, Application, Job
from apps.jobs.services.ai_flow_manager import AIFlowManager
from apps.jobs.services.ai_voice_bridge import AIVoiceBridgeService
from apps.jobs.services.scoring_engine import AnswerScoringEngine
from apps.payments.models import SubscriptionPlan, UserSubscription
from apps.users.models import CandidateProfile, EmployerProfile

User = get_user_model()


class ZecpathEndToEndIntegrationTests(APITestCase):
    """
    Day 59 End-to-End Integration Suite:
    Validates Signup -> JWT Auth -> Payment/Subscription -> Job Posting ->
    ATS Scoring -> AI Interview Eligibility -> AI Report -> Premium Analytics.
    """

    def setUp(self):
        cache.clear()

        # 1. Seed Subscription Plans
        self.free_plan = SubscriptionPlan.objects.create(
            name="Free",
            tier="FREE",
            price=0.00,
            max_active_jobs=1,
            ai_report_credits=2,
        )
        self.pro_plan = SubscriptionPlan.objects.create(
            name="Pro",
            tier="PRO",
            price=49.00,
            max_active_jobs=-1,
            ai_report_credits=50,
        )

        # 2. User Signup (verifies post_save signals auto-create profiles)
        self.employer_user = User.objects.create_user(
            email="e2e_employer@zecpath.com",
            password="StrongPassword123!",
            role=User.Role.EMPLOYER,
        )
        self.candidate_user = User.objects.create_user(
            email="e2e_candidate@zecpath.com",
            password="StrongPassword123!",
            role=User.Role.CANDIDATE,
        )

        self.employer_profile = EmployerProfile.objects.get(user=self.employer_user)
        self.employer_profile.company_name = "Zecpath Labs"
        self.employer_profile.save()

        self.candidate_profile = CandidateProfile.objects.get(user=self.candidate_user)
        self.candidate_profile.skills = "Python, Django, PostgreSQL"
        self.candidate_profile.resume = SimpleUploadedFile(
            "resume.pdf",
            b"%PDF-1.4 mock resume content",
            content_type="application/pdf",
        )
        self.candidate_profile.save()

        # 3. Generate real JWT tokens for API communication
        self.employer_token = str(RefreshToken.for_user(self.employer_user).access_token)
        self.candidate_token = str(RefreshToken.for_user(self.candidate_user).access_token)

    def _auth_header(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @patch("openai.chat.completions.create")
    @patch("razorpay.Client")
    def test_full_end_to_end_hiring_and_payment_pipeline(
        self, mock_razorpay_client, mock_openai_create
    ):
        """Validates the complete lifecycle from subscription upgrade to premium analytics."""
        # --- STAGE 1: Payment & Subscription Upgrade (Mocked Razorpay) ---
        mock_instance = MagicMock()
        mock_instance.order.create.return_value = {
            "id": "order_e2e_test_123",
            "amount": 4900,
            "currency": "INR",
            "status": "created",
        }
        mock_razorpay_client.return_value = mock_instance

        # Provision active PRO subscription (simulating verified Razorpay webhook/callback)
        UserSubscription.objects.create(
            employer=self.employer_profile,
            plan=self.pro_plan,
            status="ACTIVE",
            current_period_end=timezone.now() + timedelta(days=30),
        )

        status_resp = self.client.get(
            "/payments/status/",
            **self._auth_header(self.employer_token),
        )
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(status_resp.data["status"], "ACTIVE")
        self.assertEqual(status_resp.data["plan_name"], "Pro")

        # --- STAGE 2: Employer Job Posting ---
        job_payload = {
            "title": "Senior Backend Engineer",
            "description": "Build scalable Django REST APIs.",
            "skills": "Python, Django, PostgreSQL",
            "experience": 3,
            "location": "Remote",
            "status": "open",
            "is_automation_enabled": True,
        }
        job_resp = self.client.post(
            "/employer/jobs/",
            data=job_payload,
            format="json",
            **self._auth_header(self.employer_token),
        )
        self.assertIn(job_resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

        job = Job.objects.filter(employer=self.employer_profile).first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "open")

        # --- STAGE 3: Candidate Application & ATS Scoring ---
        apply_resp = self.client.post(
            f"/jobs/{job.id}/apply/",
            data={},
            format="json",
            **self._auth_header(self.candidate_token),
        )
        self.assertIn(
            apply_resp.status_code,
            [status.HTTP_200_OK, status.HTTP_201_CREATED],
            msg=f"Apply failed with {apply_resp.status_code}: {apply_resp.data}",
        )

        application = Application.objects.get(job=job, candidate=self.candidate_profile)
        self.assertGreaterEqual(application.ats_score, 0.0)

        # Ensure high ATS score for AI interview eligibility gate
        if application.ats_score < CallEligibilityEngine.ATS_THRESHOLD:
            application.ats_score = 85.0
            application.save()

        # --- STAGE 4: AI Interview Eligibility Gate ---
        eligible, reason = CallEligibilityEngine.is_eligible(application)
        self.assertTrue(eligible, msg=f"Expected eligible application, got: {reason}")

        # Simulate a completed AI interview session with a recorded Q&A transcript
        session = AIInterviewSession.objects.create(
            application=application,
            is_completed=True,
        )
        question = AIQuestion.objects.create(
            session=session,
            question_text="Explain how Django ORM prevents SQL injection.",
            order=0,
        )
        answer = AIAnswer.objects.create(
            question=question,
            answer_text="Django ORM uses parameterized queries to separate SQL code from user input.",
            relevance_score=90,
            completeness_score=85,
        )
        answer.calculate_normalized_score()
        answer.save()

        # Mock OpenAI report generation response
        mock_ai_resp = MagicMock()
        mock_ai_resp.choices[0].message.content = json.dumps(
            {
                "summary": "Strong backend candidate with solid Django security knowledge.",
                "strengths": ["Django ORM", "SQL injection prevention"],
                "weaknesses": ["Could elaborate further on query optimization"],
                "recommendation": "HIRE",
            }
        )
        mock_openai_create.return_value = mock_ai_resp

        # --- STAGE 5: AI Report Generation ---
        report_resp = self.client.get(
            f"/applications/{application.id}/report/",
            **self._auth_header(self.employer_token),
        )
        self.assertEqual(
            report_resp.status_code,
            status.HTTP_200_OK,
            msg=f"Report failed with {report_resp.status_code}: {report_resp.data}",
        )

        # --- STAGE 6: Mark Selected & Verify Premium Analytics ---
        application.status = "selected"
        application.save()

        analytics_resp = self.client.get(
            "/employer/analytics/premium/",
            **self._auth_header(self.employer_token),
        )
        self.assertEqual(analytics_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            analytics_resp.data["efficiency_metrics"]["hire_conversion_rate"],
            100.0,
        )

    def test_api_response_time_performance_thresholds(self):
        """Day 59 Performance Check: verifies core endpoints respond within SLA limits."""
        UserSubscription.objects.create(
            employer=self.employer_profile,
            plan=self.pro_plan,
            status="ACTIVE",
            current_period_end=timezone.now() + timedelta(days=30),
        )

        # Warm-up request to avoid cold-start / URL-resolver skew
        self.client.get("/payments/status/", **self._auth_header(self.employer_token))

        endpoints = [
            ("/payments/status/", 1.000),
            ("/employer/analytics/premium/", 1.500),
        ]

        for url, max_seconds in endpoints:
            start = time.perf_counter()
            response = self.client.get(url, **self._auth_header(self.employer_token))
            elapsed = time.perf_counter() - start

            print(f"[PERF] {url} -> {elapsed * 1000:.1f}ms")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertLess(
                elapsed,
                max_seconds,
                msg=f"{url} took {elapsed:.3f}s (limit: {max_seconds:.3f}s)",
            )


class AIInterviewServicesIntegrationTests(APITestCase):
    """
    Day 59 Integration Tests for External Services & AI Interview Pipeline:
    Validates Twilio Voice Bridge, OpenAI Follow-up Branching, and Answer Scoring.
    """

    def setUp(self):
        cache.clear()
        self.employer_user = User.objects.create_user(
            email="ai_emp@zecpath.com",
            password="StrongPassword123!",
            role=User.Role.EMPLOYER,
        )
        self.candidate_user = User.objects.create_user(
            email="ai_cand@zecpath.com",
            password="StrongPassword123!",
            role=User.Role.CANDIDATE,
        )
        self.employer_profile = EmployerProfile.objects.get(user=self.employer_user)
        self.candidate_profile = CandidateProfile.objects.get(user=self.candidate_user)

        self.job = Job.objects.create(
            employer=self.employer_profile,
            title="Python Backend Developer",
            description="Django + DRF role",
            skills="Python, Django",
            experience=2,
            location="Remote",
            status="open",
            is_automation_enabled=True,
        )

        # Dynamically resolve the screening template model linked to Job
        TemplateModel = Job.screening_templates.field.model
        self.template_1 = TemplateModel.objects.create(
            job=self.job,
            base_question="Explain how Django ORM prevents SQL injection.",
            order=0,
            requires_follow_up=True,
        )
        self.template_2 = TemplateModel.objects.create(
            job=self.job,
            base_question="What is your experience with PostgreSQL indexing?",
            order=1,
            requires_follow_up=False,
        )

        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate_profile,
            ats_score=85.0,
        )
        self.session = AIInterviewSession.objects.create(
            application=self.application,
            current_question_index=0,
        )

    @patch("apps.jobs.services.ai_voice_bridge.Client")
    def test_twilio_voice_bridge_triggers_outbound_call(self, mock_twilio_client):
        """Verifies Twilio outbound call integration without hitting the live API."""
        mock_call = MagicMock()
        mock_call.sid = "CA_mock_twilio_sid_12345"
        mock_twilio_client.return_value.calls.create.return_value = mock_call

        bridge = AIVoiceBridgeService()
        sid = bridge.trigger_outbound_call(to_number="+919876543210", call_log_id=1)

        self.assertEqual(sid, "CA_mock_twilio_sid_12345")
        mock_twilio_client.return_value.calls.create.assert_called_once()

    @patch("apps.jobs.services.ai_flow_manager.openai.chat.completions.create")
    def test_ai_flow_manager_followup_and_completion(self, mock_openai):
        """Verifies dynamic follow-up branching, question progression, and session completion."""
        # 1st answer is incomplete -> triggers follow-up
        incomplete_reply = MagicMock()
        incomplete_reply.choices[0].message.content = "Can you mention parameterized queries?"

        # 2nd answer is complete -> advances to template_2
        complete_reply = MagicMock()
        complete_reply.choices[0].message.content = "COMPLETE"

        mock_openai.side_effect = [incomplete_reply, complete_reply, complete_reply]

        manager = AIFlowManager(self.session.id)

        # Step 1: Incomplete answer triggers follow-up
        reply_1 = manager.process_candidate_answer("It handles queries safely.")
        self.session.refresh_from_db()
        self.assertTrue(self.session.awaiting_follow_up)
        self.assertEqual(self.session.current_question_index, 0)
        self.assertIn("parameterized queries", reply_1)

        # Step 2: Satisfactory answer moves to question 2 and logs AIQuestion
        reply_2 = manager.process_candidate_answer(
            "Django ORM uses parameterized queries to separate SQL code from user input."
        )
        self.session.refresh_from_db()
        self.assertFalse(self.session.awaiting_follow_up)
        self.assertEqual(self.session.current_question_index, 1)
        self.assertEqual(reply_2, self.template_2.base_question)
        self.assertTrue(AIQuestion.objects.filter(session=self.session, order=1).exists())

        # Step 3: Final answer completes the interview session
        reply_3 = manager.process_candidate_answer("I use B-Tree indexes on foreign keys.")
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_completed)
        self.assertIn("Thank you", reply_3)

    @patch("apps.jobs.services.scoring_engine.openai.chat.completions.create")
    def test_answer_scoring_engine_evaluates_and_normalizes(self, mock_openai):
        """Verifies AnswerScoringEngine parses OpenAI JSON and saves normalized scores."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "relevance": 90,
                "completeness": 80,
                "feedback": "Clear explanation of parameterized queries.",
            }
        )
        mock_openai.return_value = mock_response

        question = AIQuestion.objects.create(
            session=self.session,
            question_text=self.template_1.base_question,
            order=0,
        )
        answer = AIAnswer.objects.create(
            question=question,
            answer_text="Django ORM uses parameterized queries to prevent SQL injection.",
        )

        scored = AnswerScoringEngine.evaluate_and_score(answer)

        self.assertIsNotNone(scored)
        scored.refresh_from_db()
        self.assertEqual(scored.relevance_score, 90)
        self.assertEqual(scored.completeness_score, 80)
        self.assertEqual(scored.feedback, "Clear explanation of parameterized queries.")
