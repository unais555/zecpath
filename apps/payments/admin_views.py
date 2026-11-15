from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth, TruncDay
from apps.payments.models import PaymentTransaction, UserSubscription
from apps.payments.serializers import PaymentTransactionSerializer
import razorpay
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics


class AdminRevenueReportAPIView(views.APIView):
    """Generates financial metrics: Daily/Monthly revenue and Plan-wise splits."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        # 1. Total Revenue All-Time
        total_revenue = PaymentTransaction.objects.filter(status='SUCCESS').aggregate(
            total=Sum('amount')
        )['total'] or 0.00

        # 2. Plan-wise Revenue Split
        # Using the related_name 'subscription' on EmployerProfile (if it exists)
        # If your UserSubscription model points to EmployerProfile with related_name="subscription"
        plan_revenue = PaymentTransaction.objects.filter(status='SUCCESS').values(
            'employer__subscription__plan__name'
        ).annotate(
            total_earned=Sum('amount'),
            subscriber_count=Count('employer', distinct=True)
        ).order_by('-total_earned')

        # 3. Monthly Revenue Trend (Last 6 Months)
        monthly_trend = PaymentTransaction.objects.filter(status='SUCCESS').annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            revenue=Sum('amount')
        ).order_by('-month')[:6]

        return Response({
            "total_revenue": round(total_revenue, 2),
            "revenue_by_plan": plan_revenue,
            "monthly_trend": monthly_trend
        }, status=status.HTTP_200_OK)




class AdminTransactionListAPIView(generics.ListAPIView):
    """Lists all transactions with filtering for audits (e.g., FAILED or SUSPICIOUS)."""
    permission_classes = [IsAdminUser]
    serializer_class = PaymentTransactionSerializer
    
    def get_queryset(self):
        queryset = PaymentTransaction.objects.select_related(
            'employer', 
            'employer__user'
        ).all().order_by('-created_at')
        
        # Filter by status (e.g., ?status=FAILED to audit drops)
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
            
        # Filter by Employer ID directly on the PaymentTransaction model
        employer_id = self.request.query_params.get('employer_id', None)
        if employer_id:
            queryset = queryset.filter(employer_id=employer_id)
            
        return queryset



class AdminRefundTransactionAPIView(views.APIView):
    """Triggers a refund via Razorpay and updates the internal financial ledger."""
    permission_classes = [IsAdminUser]

    def post(self, request, transaction_id):
        transaction = get_object_or_404(PaymentTransaction, id=transaction_id)
        
        if transaction.status != 'SUCCESS':
            return Response(
                {"error": "Only successful transactions can be refunded."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Using your specific field: gateway_transaction_id
            refund = client.payment.refund(transaction.gateway_transaction_id, {
                "amount": int(transaction.amount * 100), 
                "notes": {
                    "reason": request.data.get("reason", "Admin requested refund"),
                    "admin_id": request.user.id
                }
            })
            
            # Update local database log
            transaction.status = 'REFUNDED' # Ensure 'REFUNDED' is added to your model choices if you want strict validation
            transaction.save()

            return Response({
                "message": "Refund processed successfully",
                "refund_id": refund['id']
            }, status=status.HTTP_200_OK)

        except razorpay.errors.BadRequestError as e:
            return Response({"error": f"Gateway Error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)