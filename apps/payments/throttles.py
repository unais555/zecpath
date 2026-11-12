from rest_framework.throttling import UserRateThrottle

class PremiumTierThrottle(UserRateThrottle):
    """
    Dynamically sets API rate limits based on the SaaS subscription tier.
    Protects complex analytic endpoints from abuse.
    """
    def get_rate(self):
        request = self.context.get('request')
        if not request.user.is_authenticated or not hasattr(request.user, 'employer_profile'):
            return '10/day' # Strict limit for non-employers or errors
            
        subscription = getattr(request.user.employer_profile, 'subscription', None)
        if not subscription or subscription.status != 'ACTIVE':
            return '10/day'
            
        tier = subscription.plan.tier
        if tier == 'ENT':
            return '10000/day' # Enterprise: effectively unlimited
        elif tier == 'PRO':
            return '1000/day'  # Pro: generous limit
            
        return '10/day' # Free fallback