import os
from django.core.exceptions import ValidationError


def validate_resume_size(value):
    max_size = 5 * 1024 * 1024
    if value.size > max_size:
        raise ValidationError(f"File size exceeds 5MB. Current size: {value.size / (1024*1024):.2f}MB")

def validate_resume_extentions(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.doc', '.docx']
    if ext not in valid_extensions:
        raise ValidationError(f"Unsupported file type '{ext}'. Allowed types: PDF, DOC, DOCX.")