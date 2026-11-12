from django.db import models
from django.utils import timezone
from django.conf import settings

from apps.users.models import EmployerProfile



class SubscriptionPlan(models.Model):
    """Defines the available SaaS tiers."""
    TIER_CHOICES = [('FREE', 'Free'), ('PRO', 'Pro'), ('ENT', 'Enterprise')]
    
    name = models.CharField(max_length=50)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, unique=True)
    price = models.DecimalField(max_length=10, max_digits=8, decimal_places=2)
    billing_cycle = models.CharField(max_length=10, choices=[('MONTHLY', 'Monthly'), ('YEARLY', 'Yearly')])
    max_active_jobs = models.IntegerField(default=1, help_text="-1 for unlimited")
    ai_report_credits = models.IntegerField(default=0, help_text="Monthly AI credits")
    gateway_product_id = models.CharField(max_length=100, blank=True, help_text="Stripe/Razorpay Product ID")

    def __str__(self):
        return f"{self.name} (${self.price}/{self.billing_cycle})"

class UserSubscription(models.Model):
    """Maps an Employer to a specific plan and tracks their active status."""
    employer = models.OneToOneField(EmployerProfile, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'), ('CANCELED', 'Canceled'), ('PAST_DUE', 'Past Due')
    ], default='ACTIVE')
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    gateway_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Usage Tracking (Resets every billing cycle)
    ai_reports_used_this_month = models.IntegerField(default=0)

    @property
    def is_valid(self):
        return self.status == 'ACTIVE' and self.current_period_end > timezone.now()

class PaymentTransaction(models.Model):
    """Records individual charge attempts (success or failure)."""
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=[
        ('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('PENDING', 'Pending')
    ])
    gateway_transaction_id = models.CharField(max_length=100, unique=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class BillingHistory(models.Model):
    """Generates the official invoice record for accounting purposes."""
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='invoices')
    transaction = models.OneToOneField(PaymentTransaction, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    invoice_pdf_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)