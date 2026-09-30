import os
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import CandidateProfile, EmployerProfile
from django.contrib.auth import get_user_model


User = get_user_model()

@receiver(post_save, sender=User)
def manage_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == User.Role.CANDIDATE:
            CandidateProfile.objects.create(user=instance)
        elif instance.role == User.Role.EMPLOYER:
            EmployerProfile.objects.create(user=instance)

    else:
        if instance.role == User.Role.CANDIDATE:
            if hasattr(instance, 'candidate_profile'):
                instance.candidate_profile.save()
        elif instance.role == User.Role.EMPLOYER:
            if hasattr(instance, 'employer_profile'):
                instance.employer_profile.save()

@receiver(pre_save, sender=CandidateProfile)
def auto_delete_file_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return False

    try:
        old_profile = CandidateProfile.objects.get(pk=instance.pk)
    except CandidateProfile.DoesNotExist:
        return False

    old_file = old_profile.resume
    new_file = instance.resume

    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)
