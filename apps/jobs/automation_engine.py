from django.core.mail import send_mail
from .models import Application

def send_automation_email(application, action):
    candidate_email = application.candidate.user.email
    job_title = application.job.title

    if action == 'SHORTLISTED':
        subject = f"Update on your application for {job_title}: You've been shortlisted!"
        message = "Congratulations! Your profile strongly matches our requirements. We will contact you shortly for next steps."
    elif action == 'REJECTED':
        subject = f"Update on your application for {job_title}"
        message = "Thank you for applying. Unfortunately, we will not be moving forward with your application at this time."

        send_mail(subject, message, 'zecpath@ats.com', [candidate_email], fail_silently=True)

    
def process_application_automation(application_id):
    application = Application.objects.select_related('job', 'candidate__user').get(id=application_id)
    job = application.job

    if not job.is_automation_enabled or application.is_manually_overridden:
        return

    if application.ats_score >= job.auto_shortlist_threshold:
        application.status = 'SHORTLISTED'
        application.save(update_fields=['status'])
        send_automation_email(application, 'SHORTLISTED')
    elif application.ats_score < job.auto_reject_threshold:
        application.status = 'REJECTED'
        application.save(update_fields=['status'])
        send_automation_email(application, "REJECTED")