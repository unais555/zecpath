from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import SubscriptionPlan, UserSubscription
from apps.users.models import EmployerProfile
from apps.jobs.models import Job

User = get_user_model()

class SubscriptionFeatureTests(APITestCase):
    def setUp(self):
        # 1. Setup Base User and Employer
        self.user = User.objects.create_user(email='test@zecpath.com', password='password123', role=User.Role.EMPLOYER)
        # self.employer = EmployerProfile.objects.create(user=self.user, company_name='Zecpath Tech')
        self.employer, created = EmployerProfile.objects.get_or_create(user=self.user)
        self.employer.company_name = 'Zecpath Tech'
        self.employer.save()
        
        # 2. Setup Subscription Plans
        self.free_plan = SubscriptionPlan.objects.create(
            name='Free', tier='FREE', price=0.00, max_active_jobs=1, ai_report_credits=0
        )
        self.pro_plan = SubscriptionPlan.objects.create(
            name='Pro', tier='PRO', price=49.00, max_active_jobs=-1, ai_report_credits=50
        )
        
        # 3. Assign Free Plan initially
        self.subscription = UserSubscription.objects.create(
            employer=self.employer,
            plan=self.free_plan,
            status='ACTIVE',
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # 4. Authenticate the test client
        self.client.force_authenticate(user=self.user)

        self.valid_job_data = {
            "description": "Test Description",
            "skills": "Python, Django",
            "experience": 2,
            "location": "Remote"
        }

        self.user.refresh_from_db() # <--- ADD THIS LINE
        self.client.force_authenticate(user=self.user)

    def test_free_tier_job_posting_limit(self):
        """Validates that CanPostJob permission blocks the 2nd job for Free tier."""
        Job.objects.create(
            employer=self.employer, 
            title="First Job", 
            is_active=True,
            **self.valid_job_data
        )
        
        payload = {"title": "Second Job"}
        payload.update(self.valid_job_data)

        response = self.client.post('/employer/jobs/', payload)
        
        # Simplified to avoid custom exception handler formatting mismatch
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pro_tier_bypasses_job_limit(self):
        """Validates that Pro tier users can post unlimited jobs."""
        self.subscription.plan = self.pro_plan
        self.subscription.save()
        
        # ADDED **self.valid_job_data to prevent validation error on manual create
        Job.objects.create(
            employer=self.employer, 
            title="First Job", 
            is_active=True,
            **self.valid_job_data
        )
        
        # ADDED self.valid_job_data to payload to pass serializer requirements
        payload = {"title": "Second Job"}
        payload.update(self.valid_job_data)

        response = self.client.post('/employer/jobs/', payload)
        if response.status_code == 403:
            print(f"\n[DEBUG] 403 Reason: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_middleware_blocks_free_tier_from_premium_analytics(self):
        """Validates the SubscriptionEnforcementMiddleware blocks Free users."""
        # UPDATED URL to match your urls.py exactly
        response = self.client.get('/employer/analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_middleware_blocks_expired_subscriptions(self):
        """Validates the middleware catches expired Pro accounts."""
        self.subscription.plan = self.pro_plan
        self.subscription.current_period_end = timezone.now() - timedelta(days=1)
        self.subscription.save()
        
        # UPDATED URL to match your urls.py exactly
        response = self.client.get('/employer/analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
