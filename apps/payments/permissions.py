from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from apps.jobs.models import Job

class HasAvailableAICredits(BasePermission):
    """
    Checks if the employer has a valid subscription and remaining AI credits
    before firing the OpenAI Celery task.
    """
    message = "Upgrade to Pro or purchase additional credits to generate AI Candidate Reports."

    def has_permission(self, request, view):
        subscription = getattr(request.user.employer_profile, 'subscription', None)
        
        if not subscription or not subscription.is_valid:
            return False
            
        if subscription.plan.tier == 'ENT':
            return True # Enterprise has unlimited access
            
        if subscription.plan.tier == 'PRO':
            return subscription.ai_reports_used_this_month < subscription.plan.ai_report_credits
            
        return False # Free tier denied


class CanPostJob(BasePermission):
    """Enforces job posting limits based on the employer's subscription tier."""
    message = "You have reached the maximum active job posts for your plan. Please upgrade."

    def has_permission(self, request, view):
        # Allow GET requests (viewing jobs) for everyone
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
            
        # 1. Correctly fetch using the related_name="employer_profile"
        if not hasattr(request.user, 'employer_profile'):
            return False
            
        employer = request.user.employer_profile
        subscription = getattr(employer, 'subscription', None)
        
        if not subscription or subscription.status != 'ACTIVE':
            return False
            
        if subscription.plan.max_active_jobs == -1: # Unlimited (Pro/Enterprise)
            return True
            
        # Count active jobs for Free tier
        active_jobs = Job.objects.filter(employer=employer, is_active=True).count()
        return active_jobs < subscription.plan.max_active_jobs




class RequiresPremiumSubscription(BasePermission):
    """Blocks Free tier or expired subscriptions from accessing premium analytics."""
    
    def has_permission(self, request, view):
        if not hasattr(request.user, 'employer_profile'):
            self.message = "Only employers can access this resource."
            return False
            
        subscription = getattr(request.user.employer_profile, 'subscription', None)
        
        if not subscription or subscription.status != 'ACTIVE':
            self.message = "Premium features require an active subscription."
            return False
            
        if subscription.current_period_end < timezone.now():
            self.message = "Your billing period has ended. Please renew."
            return False
            
        if subscription.plan.tier == 'FREE':
            self.message = "Analytics are only available on Pro and Enterprise tiers."
            return False
            
        return True

class CanGenerateAIReport(BasePermission):
    """Monetization Logic: Enforces AI credit limits for candidate evaluation."""
    message = "Insufficient AI credits. Upgrade your plan to generate more reports."

    def has_permission(self, request, view):
        if not hasattr(request.user, 'employer_profile'):
            return False
            
        subscription = getattr(request.user.employer_profile, 'subscription', None)
        if not subscription or subscription.status != 'ACTIVE':
            return False
            
        if subscription.plan.tier == 'ENT':
            return True
            
        if subscription.plan.tier == 'PRO':
            return subscription.ai_reports_used_this_month < subscription.plan.ai_report_credits
            
        return False