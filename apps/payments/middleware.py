from django.http import JsonResponse
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class SubscriptionEnforcementMiddleware:
    """
    Intercepts requests to ensure employers have an active paid subscription
    before accessing premium routes (supports both Session and JWT auth).
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Leading slash is required to match request.path
        self.restricted_paths = [
            "/employer/analytics/",
            "/employer/analytics/premium/",
        ]

    def _get_authenticated_user(self, request):
        """Return session user if logged in, otherwise resolve JWT Bearer token."""
        if request.user.is_authenticated:
            return request.user

        try:
            auth_result = JWTAuthentication().authenticate(request)
        except (InvalidToken, AuthenticationFailed):
            # Let DRF's view authentication return the standard 401 response
            return None

        if auth_result is not None:
            user, _token = auth_result
            return user
        return None

    def __call__(self, request):
        if any(request.path.startswith(path) for path in self.restricted_paths):
            user = self._get_authenticated_user(request)

            if user and user.is_authenticated and hasattr(user, "employer_profile"):
                subscription = getattr(user.employer_profile, "subscription", None)

                # 1. Check if subscription exists and is active
                if not subscription or subscription.status != "ACTIVE":
                    return JsonResponse(
                        {
                            "error": "Payment Required",
                            "message": (
                                "Your subscription is inactive or past due. "
                                "Please update your billing."
                            ),
                        },
                        status=402,
                    )

                # 2. Block Free tier from premium analytics
                if subscription.plan.tier == "FREE":
                    return JsonResponse(
                        {
                            "error": "Upgrade Required",
                            "message": (
                                "Premium analytics require a Pro or Enterprise subscription."
                            ),
                        },
                        status=403,
                    )

                # 3. Strict date enforcement layer
                if subscription.current_period_end < timezone.now():
                    return JsonResponse(
                        {
                            "error": "Subscription Expired",
                            "message": "Your billing period has ended.",
                        },
                        status=403,
                    )

        return self.get_response(request)
