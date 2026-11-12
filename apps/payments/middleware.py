from django.http import JsonResponse
from django.utils import timezone

class SubscriptionEnforcementMiddleware:
    """
    Intercepts requests to ensure employers have an active subscription 
    before accessing premium routes.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Define URL prefixes that require an active subscription
        self.restricted_paths = [
            'applications/<int:application_id>/report/',
            'employer/analytics/',
            'employer/analytics/premium/'
            ]

    def __call__(self, request):
        # Only check restricted paths to save database queries
        if any(request.path.startswith(path) for path in self.restricted_paths):
            if request.user.is_authenticated and hasattr(request.user, 'employer_profile'):
                subscription = getattr(request.user.employer_profile, 'subscription', None)
                
                # Check if subscription exists and is not past due/canceled
                if not subscription or subscription.status != 'ACTIVE':
                    return JsonResponse({
                        "error": "Payment Required",
                        "message": "Your subscription is inactive or past due. Please update your billing."
                    }, status=402)
                    
                # Strict date enforcement layer
                if subscription.current_period_end < timezone.now():
                    return JsonResponse({
                        "error": "Subscription Expired",
                        "message": "Your billing period has ended."
                    }, status=403)
                    
        return self.get_response(request)