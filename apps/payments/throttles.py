from rest_framework.throttling import UserRateThrottle


class PremiumTierThrottle(UserRateThrottle):
    """Applies higher API rate limits for Pro and Enterprise subscribers."""

    scope = "premium_tier"

    def get_rate(self):
        # Fallback rate used during __init__ before request is available
        return "60/hour"

    def allow_request(self, request, view):
        if request.user and request.user.is_authenticated:
            employer = getattr(request.user, "employer_profile", None)
            subscription = getattr(employer, "subscription", None) if employer else None
            tier = subscription.plan.tier if subscription and subscription.plan else "FREE"

            tier_rates = {
                "ENTERPRISE": "1000/hour",
                "PRO": "300/hour",
                "FREE": "60/hour",
            }
            self.rate = tier_rates.get(tier, "60/hour")
            self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)
