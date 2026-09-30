from django.db import models
import uuid
import os
from .validators import validate_resume_extentions, validate_resume_size
from django.contrib.auth.models import AbstractUser, BaseUserManager


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

def resume_upload_path(instance, filename):
    ext = filename.split('.')[-1].lower()
    new_filename = f"candidate_{instance.user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    return f"resumes/{new_filename}"


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EMPLOYER = "employer", "Employer"
        CANDIDATE = "candidate", "Candidate"

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=15, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email



class EmployerProfile(models.Model):
    class CompanySize(models.TextChoices):
        MICRO = "1-10", "1-10 employees"
        SMALL = "11-50", "11-50 employees"
        MEDIUM = "51-200", "51-200 employees"
        LARGE = "201-500", "201-500 employees"
        ENTERPRISE = "500+", "500+ employees"
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employer_profile")
    company_name = models.CharField(max_length=255)
    domain = models.CharField(max_length=100, help_text="e.g., IT, Healthcare, Finance", blank=True)
    size = models.CharField(max_length=20, choices=CompanySize.choices, blank=True)
    is_verified = models.BooleanField(
        default=False, 
        help_text="Indicates if the company's identity has been vetted."
    )

    def __str__(self):
        return f"{self.company_name} ({self.user.email})"


class CandidateProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="candidate_profile")
    resume = models.FileField(
        upload_to=resume_upload_path,
        validators=[validate_resume_size, validate_resume_extentions],
        blank = True,
        null= True,
    )
    skills = models.TextField(
        blank=True, 
        help_text="Comma-separated list of skills (e.g., Python, Django, React)"
    )
    education = models.TextField(
        blank=True, 
        help_text="Details of degrees, certifications, and institutions"
    )
    experience = models.PositiveIntegerField(
        default=0, 
        help_text="Total years of professional experience"
    )
    expected_salary = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Expected annual salary"
    )

    def __str__(self):
        return f"Candidate Profile for {self.user.email}"
    