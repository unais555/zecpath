from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import NotificationLog

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_async_email(self, recipient_email, subject, template_name, context, event_type):
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