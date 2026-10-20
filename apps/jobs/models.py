from django.db import models
from apps.users.models import EmployerProfile
from django.core.exceptions import ValidationError
from apps.users.models import CandidateProfile
from django.conf import settings



class Job(models.Model):
    class JobType(models.TextChoices):
        PART_TIME = "part_time", "Part_time"
        FULLL_TIME = "full_time", "Full_time"
        INTERNSHIP = "intership", "Internship"

    class JobStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    skills = models.CharField(max_length=255, db_index=True)
    experience = models.PositiveIntegerField()
    min_salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    location = models.CharField(max_length=255)
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULLL_TIME)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.DRAFT, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    auto_shortlist_threshold = models.IntegerField(default=80, help_text="ATS score (0-100) required to automatically shortlist.")
    auto_reject_threshold = models.IntegerField(default=40, help_text="ATS score (0-100) below which candidates are automatically rejected.")
    is_automation_enabled = models.BooleanField(default=True)
    
    def clean(self):
        if self.min_salary and self.max_salary and self.min_salary > self.max_salary:
            raise ValidationError({"max_salary": "Maximum salary cannot be less than minimum salary."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.id} - {self.title} at {self.employer.company_name}"


class Application(models.Model):
    class ApplicationStatus(models.TextChoices):
        APPLIED = 'applied', 'Applied'
        SHORTLISTED = 'shortlisted', 'Shortlisted'
        INTERVIEW_SCHEDULED = 'interview_scheduled', 'Interview Scheduled'
        REJECTED = 'rejected', 'Rejected'
        SELECTED = 'selected', 'Selected'

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='applications')

    resume_snapshot = models.URLField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.APPLIED)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    ats_score = models.IntegerField(default=0)
    is_manually_overridden = models.BooleanField(default=False)

    class Meta:
        indexes = [
            # Speeds up finding applications for a specific job by status
            models.Index(fields=['job', 'status']),
            # Speeds up the employer dashboard ranking (-ats_score descending)
            models.Index(fields=['-ats_score']), 
        ]
        constraints = [
            models.UniqueConstraint(fields=['job', 'candidate'], name='unique_job_application')
        ]

    def __str__(self):
        return f"{self.id} - {self.candidate.user.email} -> {self.job.title}"



class ApplicationLog(models.Model):

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='status_logs')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    old_status = models.CharField(max_length=30, choices=Application.ApplicationStatus.choices)
    new_status = models.CharField(max_length=30, choices=Application.ApplicationStatus.choices)
    notes = models.TextField(blank=True, help_text="Optional feedback from the employer.")
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application.candidate.user.email} -> {self.new_status}"


class SavedJob(models.Model):
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'job'], name='unique_saved_jobs')
        ]
    def __str__(self):
        return f"{self.candidate.user.email} saved {self.job.title}"



class NotificationLog(models.Model):
    EVENT_CHOICES = [
        ("APPLIED", "Applicatin submitted"),
        ("SHORTLISTED", "Candidate shortlisted"),
        ('REJECTED', 'Candidate Rejected'),
    ]

    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    status = models.CharField(max_length=20, default='PENDING')
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.recipient} - {self.status}"