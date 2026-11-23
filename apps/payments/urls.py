from django.urls import path

from .admin_views import (
    AdminRefundTransactionAPIView,
    AdminRevenueReportAPIView,
    AdminTransactionListAPIView,
)
from .views import (
    CreatePaymentOrderAPIView,
    SubscriptionStatusAPIView,
    VerifyPaymentAPIView,
    razorpay_webhook,
)

urlpatterns = [
    path(
        "order/create/",
        CreatePaymentOrderAPIView.as_view(),
        name="create-payment-order",
    ),
    path("order/verify/", VerifyPaymentAPIView.as_view(), name="verify-payment"),
    path("status/", SubscriptionStatusAPIView.as_view(), name="subscription-status"),
    # Server-to-Server Webhook (No Authentication required, verified via signature)
    path("webhook/razorpay/", razorpay_webhook, name="razorpay-webhook"),
    path(
        "admin/revenue/",
        AdminRevenueReportAPIView.as_view(),
        name="admin-revenue-report",
    ),
    path(
        "admin/transactions/",
        AdminTransactionListAPIView.as_view(),
        name="admin-transactions",
    ),
    path(
        "admin/transactions/<int:transaction_id>/refund/",
        AdminRefundTransactionAPIView.as_view(),
        name="admin-refund",
    ),
]
