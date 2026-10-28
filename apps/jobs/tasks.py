from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import NotificationLog
import time
from django.utils import timezone
from .models import Application, AICallLog
from .eligibility import CallEligibilityEngine
from .services.ai_voice_bridge import AIVoiceBridgeService, RateLimitError, AIVoiceAPIError

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_async_email(self, recipient_email, subject, template_name, context, event_type):
    print(f"Starting to send email to {recipient_email}...")
    log = NotificationLog.objects.create(
        recipient=recipient_email,
        subject=subject,
        event_type=event_type,
        status='PENDING'
    )

    try:
        #Render HTML and plain text templates
        html_content = render_to_string(f"emails/{template_name}.html", context)
        text_content = render_to_string(f"emails/{template_name}.txt", context)
        
        #Construct and send the email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email='ats@yourcompany.com',
            to=[recipient_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
    
        log.status = 'SUCCESS'
        log.save(update_fields=['status'])
        
    except Exception as e:
        #Log the failure and trigger a retry
        log.status = 'FAILED'
        log.error_message = str(e)
        log.save(update_fields=['status', 'error_message'])
        raise self.retry(exc=e)
    

@shared_task
def parse_resume_task(application_id):
    """Simulates a heavy AI NLP text extraction process."""
    print(f"Parsing resume for Application {application_id}...")
    time.sleep(5) # Simulating heavy processing
    print(f"Resume {application_id} parsed successfully!")
    return "NLP_EXTRACTION_COMPLETE"


@shared_task
def trigger_ai_voice_call(candidate_phone, job_id):
    """Pings the Voice API (like Twilio) to start the AI interview."""
    print(f"Initiating AI Voice Call to {candidate_phone} for Job {job_id}...")
    # Logic to hit AI Voice Service will go here tomorrow
    return "CALL_INITIATED"


@shared_task(bind=True, max_retries=3, default_retry_delay=300) # Retry every 5 mins on failure
def process_ai_call_trigger(self, application_id):
    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        return "Application not found"

    is_eligible, reason = CallEligibilityEngine.is_eligible(application)
    if not is_eligible:
        print(f"Skipping call for App {application_id}: {reason}")
        return reason

    scheduled_time = CallEligibilityEngine.get_valid_call_window()

    call_log, created = AICallLog.objects.get_or_create(application=application)
    call_log.scheduled_for = scheduled_time
    call_log.status = AICallLog.CallStatus.QUEUED
    call_log.save()

    if scheduled_time > timezone.localtime(timezone.now()):
        delay_seconds = (scheduled_time - timezone.localtime(timezone.now())).total_seconds()
        print(f"Outside business hours. Scheduling call for {scheduled_time} (in {delay_seconds} seconds)")

        execute_external_call.apply_async(args=[call_log.id], countdown=delay_seconds)
        return f"Scheduled for {scheduled_time}"

    execute_external_call.delay(call_log.id)
    return "Triggered immediately"

@shared_task(bind=True)
def execute_external_call(self, call_log_id):
    """This task actually pings Twilio/OpenAI."""
    call_log = AICallLog.objects.get(id=call_log_id)
    candidate_phone = call_log.application.candidate.phone_number
    
    call_log.status = AICallLog.CallStatus.IN_PROGRESS
    call_log.save(update_fields=['status'])

    bridge = AIVoiceBridgeService()

    try:
        provider_sid = bridge.trigger_outbound_call(
            to_number=candidate_phone, 
            call_log_id=call_log.id,
            language='en-IN' 
        )

        call_log.provider_call_sid = provider_sid
        call_log.save(update_fields=['provider_call_sid'])
        return f"Call API Pinged successfully. SID: {provider_sid}"
        
    except (AIVoiceAPIError, RateLimitError) as e:
        call_log.status = AICallLog.CallStatus.FAILED
        call_log.retry_count += 1
        call_log.save(update_fields=['status', 'retry_count'])
        
        # Celery-level retry if the Service Bridge exhausted its internal retries
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 60)
    
