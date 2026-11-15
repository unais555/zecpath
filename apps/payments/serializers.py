from rest_framework import serializers
from apps.payments.models import PaymentTransaction

class PaymentTransactionSerializer(serializers.ModelSerializer):
    # Flattening related fields so admins can see who made the transaction instantly
    company_name = serializers.CharField(source='employer.company_name', read_only=True)
    employer_email = serializers.EmailField(source='employer.user.email', read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 
            'employer', 
            'company_name', 
            'employer_email', 
            'amount', 
            'currency', 
            'status', 
            'gateway_transaction_id', 
            'error_message', 
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']