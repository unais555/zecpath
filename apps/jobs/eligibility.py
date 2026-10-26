from django.utils import timezone
import datetime

class CallEligibilityEngine:
    ATS_THRESHOLD = 70.0
    MAX_RETRIES = 3

    @classmethod
    def is_eligible(cls, application):
        # job status validation
        if application.job.status != 'OPEN' or not application.job.is_automation_enabled:
            return False

        # ATS threshold 
        if application.ats_score < cls.ATS_THRESHOLD:
            return False

        # Prevent Duplication
        if hasattr(application, 'ai_call'):
            if application.ai_calls.status in ['QUEUED', 'IN_PROGRESS', 'COMPLETED']:
                return False
            if application.ai_call.retry_count >= cls.MAX_RETRIES:
                return False, "Max retry limit reached."

        return True, "Eligible"

    @classmethod
    def get_valid_call_window(cls):
        now = timezone.localtime(timezone.now())

        if now.hour < 9:
            return now.replace(hour=9, minute=0, second=0, microsecond=0)

        if now.hour >= 18:
            tomorrow = now + datetime.timedelta(days=1)
            return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

        return now