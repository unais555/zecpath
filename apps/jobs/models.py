from django.db import models
from apps.users.models import EmployerProfile
from django.core.exceptions import ValidationError



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
    title = models.CharField(max_length=255)
    description = models.TextField()
    skills = models.CharField(max_length=255)
    experience = models.PositiveIntegerField()
    min_salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    location = models.CharField(max_length=255)
    job_type = models.CharField(max_length=20, choices=JobType.choices, default=JobType.FULLL_TIME)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.DRAFT)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        if self.min_salary and self.max_salary and self.min_salary > self.max_salary:
            raise ValidationError({"max_salary": "Maximum salary cannot be less than minimum salary."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} at {self.employer.company_name}"



