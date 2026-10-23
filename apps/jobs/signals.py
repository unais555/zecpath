from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Application
from .tasks import send_async_email

@receiver(post_save, sender=Application)
def trigger_application_notifications(sender, instance, created, **kwargs):
    candidate_email = instance.candidate.user.email
    candidate_name = instance.candidate.user.first_name
    job_title = instance.job.title
    
    context = {'candidate_name': candidate_name, 'job_title': job_title}


    if created:
        # send_async_email.delay(  => with redis
        send_async_email.delay(
            recipient_email=candidate_email,
            subject=f"Application Received: {job_title}",
            template_name="application_received",
            context=context,
            event_type='APPLIED'
        )
        return


    if instance.tracker.has_changed('status'):
        if instance.status == Application.ApplicationStatus.SHORTLISTED:
            send_async_email.delay(
                recipient_email=candidate_email,
                subject=f"Great news! You've been shortlisted for {job_title}",
                template_name="application_shortlisted",
                context=context,
                event_type='SHORTLISTED'
            )
        elif instance.status == Application.ApplicationStatus.REJECTED:
            send_async_email.delay(
                recipient_email=candidate_email,
                subject=f"Update regarding your application for {job_title}",
                template_name="application_rejected",
                context=context,
                event_type='REJECTED'
            )