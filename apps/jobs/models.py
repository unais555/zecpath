from django.db import models
from apps.users.models import EmployerProfile
from django.core.exceptions import ValidationError
from apps.users.models import CandidateProfile
from django.conf import settings
from django.utils import timezone



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



class AICallLog(models.Model):
    class CallStatus(models.TextChoices):
        QUEUED = 'QUEUED', 'Queued'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        NO_ANSWER = 'NO_ANSWER', 'No Answer'

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='ai_call')
    status = models.CharField(max_length=20, choices=CallStatus.choices, default=CallStatus.QUEUED)
    provider_call_sid = models.CharField(max_length=100, blank=True, null=True) # E.g., Twilio Call ID
    scheduled_for = models.DateTimeField(default=timezone.now)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Call {self.id} - {self.application.candidate.user.email} - {self.status}"


class AIInterviewSession(models.Model):
    application = models.OneToOneField('Application', on_delete=models.CASCADE, related_name='interview_session')
    call_log = models.OneToOneField('AICallLog', on_delete=models.SET_NULL, null=True, related_name='session')
    
    # Transcript Storage (Structured JSON)
    full_transcript_raw = models.JSONField(default=list, blank=True, help_text="Raw structured JSON array of all conversation turns.")
    
    # Audit Logs: Who, When, Why
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="The user who manually triggered the call. Null if system auto-triggered."
    )
    trigger_reason = models.CharField(max_length=255, default="System Auto-Trigger: ATS Score >= 70")
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_duration_seconds(self):
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return 0

    def __str__(self):
        return f"Interview Session - {self.application.candidate.user.email}"


class AIQuestion(models.Model):
    """Tracks each individual question asked by the AI."""
    session = models.ForeignKey(AIInterviewSession, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    order = models.PositiveIntegerField(help_text="The sequence number of the question.")
    asked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."


class AIAnswer(models.Model):
    """Tracks the voice-to-text transcript output of the candidate's response."""
    question = models.OneToOneField(AIQuestion, on_delete=models.CASCADE, related_name='answer')
    answer_text = models.TextField(help_text="The Speech-to-Text (STT) output of the candidate's voice.")
    
    # AI Evaluation of the specific answer
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True, null=True)
    
    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Answer to Q{self.question.order}"