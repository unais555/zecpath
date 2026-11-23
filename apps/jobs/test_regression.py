from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.jobs.eligibility import CallEligibilityEngine
from apps.jobs.models import Application, Job
from apps.payments.models import SubscriptionPlan, UserSubscription
from apps.users.models import CandidateProfile, EmployerProfile

User = get_user_model()


class Day58RegressionTests(APITestCase):
    def setUp(self):
        self.employer_user = User.objects.create_user(
            email="reg_emp@test.com",
            password="password123",
            role=User.Role.EMPLOYER,
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(
            user=self.employer_user,
            defaults={"company_name": "Regression Tech"},
        )

        self.candidate_user = User.objects.create_user(
            email="reg_cand@test.com",
            password="password123",
            role=User.Role.CANDIDATE,
        )
        self.candidate_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate_user,
        )

        self.pro_plan = SubscriptionPlan.objects.create(
            name="Pro",
            tier="PRO",
            price=49.00,
            max_active_jobs=-1,
            ai_report_credits=50,
        )
        UserSubscription.objects.create(
            employer=self.employer_profile,
            plan=self.pro_plan,
            status="ACTIVE",
            current_period_end=timezone.now() + timedelta(days=30),
        )

        self.job = Job.objects.create(
            employer=self.employer_profile,
            title="Senior Django Dev",
            description="Backend role",
            skills="Python, Django",
            experience=3,
            location="Remote",
            status="open",
            is_automation_enabled=True,
        )
        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate_profile,
            status="selected",
            ats_score=85.0,
        )

    def test_eligibility_accepts_lowercase_open_job(self):
        """Regression test: eligibility.py must recognize lowercase 'open' job status."""
        eligible, _reason = CallEligibilityEngine.is_eligible(self.application)
        self.assertTrue(eligible)

    def test_premium_analytics_counts_selected_applications(self):
        """Regression test: PremiumAnalyticsAPIView uses employer_profile and lowercase 'selected'."""
        self.client.force_authenticate(user=self.employer_user)
        self.client.force_login(self.employer_user)

        response = self.client.get("/employer/analytics/premium/")  # adjust to your exact URL

        # Verify the 'selected' application is counted rather than returning 0
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["efficiency_metrics"]["hire_conversion_rate"], 100.0)
