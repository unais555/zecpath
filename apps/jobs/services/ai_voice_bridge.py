import logging
import time
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

class AIVoiceAPIError(Exception):
    pass

class RateLimitError(Exception):
    pass

class AIVoiceBridgeService:
    def __init__(self):
        self.twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.max_retries = 3

    def trigger_outbound_call(self, to_number, call_log_id, language='en-IN', voice='Polly.Raveena'):
        """
        Triggers the outbound call via Twilio.
        Includes Voice/Language selection (Default: Indian English 'en-IN', Raveena voice).
        """
        # The webhook URL Twilio will ping when the user picks up the phone 
        webhook_url = f"https://your-server.com/api/voice/webhook/{call_log_id}/"

        for attempt in range(self.max_retries):
            try:
                call = self.twilio_client.calls.create(
                    to=to_number,
                    from_=self.from_number,
                    url=webhook_url, # Points Twilio to your Django app for instructions
                    machine_detection="Enable", # Detects if voicemail picks up
                    timeout=30 # Ring duration before failing
                )
                logger.info(f"Call initiated successfully: SID {call.sid}")
                return call.sid
            except TwilioRestException as e:
                self._handle_api_exception(e, attempt)

    def _handle_api_exception(self, e, attempt):
        """Centralized error handling and retry fallback logic."""
        if e.status == 429:
            logger.warning(f"Rate limited by Twilio. Attempt {attempt + 1} of {self.max_retries}")
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt) # Exponential backoff: 1s, 2s, 4s
                return
            raise RateLimitError("Twilio Rate Limit Exceeded after retries.")
        
        elif e.status >= 500:
            logger.error(f"Provider API down. Attempt {attempt + 1} of {self.max_retries}")
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)
                return
            raise AIVoiceAPIError("Voice Provider Internal Server Error.")
        
        else:
            # 400 errors (e.g., invalid phone number format) should fail immediately, no retry
            logger.error(f"Bad Request to Voice Provider: {e.msg}")
            raise AIVoiceAPIError(f"API Error: {e.msg}")