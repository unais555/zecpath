import razorpay
from django.conf import settings
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import SubscriptionPlan, PaymentTransaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from datetime import timezone



# Initialize Razorpay Client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class CreatePaymentOrderAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id')
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        # Razorpay expects amounts in the smallest currency subunit (paise for INR, cents for USD)
        amount_in_paise = int(plan.price * 100) 
        
        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR", # or USD
            "receipt": f"receipt_{request.user.id}_{plan.id}",
            "payment_capture": "1" # Auto-capture the payment
        })
        
        # Log the attempt in your database (from Day 46 Schema)
        PaymentTransaction.objects.create(
            employer=request.user.employer_profile,
            amount=plan.price,
            status='PENDING',
            gateway_transaction_id=razorpay_order['id']
        )
        
        return Response({
            "order_id": razorpay_order['id'],
            "amount": amount_in_paise,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID
        }, status=status.HTTP_201_CREATED)



class VerifyPaymentAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('razorpay_payment_id')
        order_id = request.data.get('razorpay_order_id')
        signature = request.data.get('razorpay_signature')
        
        try:
            # 1. MATHEMATICAL SIGNATURE VERIFICATION
            # If this fails, razorpay throws a SignatureVerificationError
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
            
            # 2. Update Database
            transaction = PaymentTransaction.objects.get(gateway_transaction_id=order_id)
            transaction.status = 'SUCCESS'
            transaction.save()
            
            # 3. Upgrade the Employer's Account
            employer_sub = request.user.employer_profile.subscription
            # Logic to upgrade to PRO/ENT goes here...
            
            return Response({"message": "Payment verified and account upgraded!"}, status=status.HTTP_200_OK)
            
        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Fraudulent payment detected. Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)



class SubscriptionStatusAPIView(views.APIView):
    """Returns the employer's current plan, status, and usage limits."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'employer'):
            return Response({"error": "Only employers have billing profiles."}, status=status.HTTP_403_FORBIDDEN)
            
        subscription = getattr(request.user.employer, 'subscription', None)
        
        if not subscription:
            return Response({"status": "NO_SUBSCRIPTION"}, status=status.HTTP_200_OK)

        return Response({
            "plan_name": subscription.plan.name,
            "tier": subscription.plan.tier,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "is_expired": subscription.current_period_end < timezone.now(),
            "usage": {
                "max_jobs": "Unlimited" if subscription.plan.max_active_jobs == -1 else subscription.plan.max_active_jobs,
                "ai_credits_total": "Unlimited" if subscription.plan.tier == 'ENT' else subscription.plan.ai_report_credits,
                "ai_credits_used": subscription.ai_reports_used_this_month
            }
        }, status=status.HTTP_200_OK)


@csrf_exempt # Webhooks come from outside, so no CSRF token
def razorpay_webhook(request):
    if request.method == "POST":
        webhook_body = request.body.decode('utf-8')
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        
        try:
            # Verify the webhook actually came from Razorpay
            client.utility.verify_webhook_signature(
                webhook_body, 
                webhook_signature, 
                settings.RAZORPAY_WEBHOOK_SECRET
            )
            
            import json
            payload = json.loads(webhook_body)
            event_type = payload.get('event')
            
            if event_type == 'payment.captured':
                order_id = payload['payload']['payment']['entity']['order_id']
                # Mark transaction as SUCCESS in DB if not already done by frontend
                
            elif event_type == 'payment.failed':
                order_id = payload['payload']['payment']['entity']['order_id']
                # Mark transaction as FAILED in DB, alert user
                
            return HttpResponse(status=200)
            
        except razorpay.errors.SignatureVerificationError:
            return HttpResponse(status=400) # Reject fake webhooks


