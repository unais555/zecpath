from django.http import JsonResponse
from django.utils import timezone


class SubscriptionEnforcementMiddleware:
    """
    Intercepts requests to ensure employers have an active paid subscription
    before accessing premium routes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Leading slash is required to match request.path
        self.restricted_paths = [
            "/employer/analytics/",
            "/employer/analytics/premium/",
        ]

    def __call__(self, request):
        if (
            any(request.path.startswith(path) for path in self.restricted_paths)
            and request.user.is_authenticated
            and hasattr(request.user, "employer_profile")
        ):
            subscription = getattr(request.user.employer_profile, "subscription", None)

            # 1. Check if subscription exists and is active
            if not subscription or subscription.status != "ACTIVE":
                return JsonResponse(
                    {
                        "error": "Payment Required",
                        "message": "Your subscription is inactive or past due. Please update your billing.",
                    },
                    status=402,
                )

            # 2. Block Free tier from premium analytics
            if subscription.plan.tier == "FREE":
                return JsonResponse(
                    {
                        "error": "Upgrade Required",
                        "message": "Premium analytics require a Pro or Enterprise subscription.",
                    },
                    status=403,
                )

            # 3. Strict date enforcement layer (un-indented so it actually runs)
            if subscription.current_period_end < timezone.now():
                return JsonResponse(
                    {
                        "error": "Subscription Expired",
                        "message": "Your billing period has ended.",
                    },
                    status=403,
                )

        return self.get_response(request)
