from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import UserSubscription
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_subscription_expirations():
    """
    Daily cron task to check for expired subscriptions and apply grace periods.
    """
    now = timezone.now()
    
    # 1. Identify subscriptions that expired today
    expired_subs = UserSubscription.objects.filter(
        status='ACTIVE',
        current_period_end__lt=now
    )
    
    for sub in expired_subs:
        # Move to PAST_DUE to trigger the 3-day grace period
        sub.status = 'PAST_DUE'
        sub.save()
        logger.info(f"Subscription {sub.id} marked as PAST_DUE.")
        # Trigger an email alert to the employer here (send_async_email.delay(...))
        
    # 2. Identify subscriptions that have exceeded the 3-day grace period
    grace_period_end = now - timedelta(days=3)
    defaulted_subs = UserSubscription.objects.filter(
        status='PAST_DUE',
        current_period_end__lt=grace_period_end
    )
    
    for sub in defaulted_subs:
        # Hard lock the account by reverting to Free tier or Canceling
        sub.status = 'CANCELED'
        # Optional: Downgrade logic
        # free_plan = SubscriptionPlan.objects.get(tier='FREE')
        # sub.plan = free_plan
        # sub.status = 'ACTIVE'
        sub.save()
        logger.info(f"Subscription {sub.id} CANCELED after grace period expiration.")