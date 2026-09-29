from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def is_employer(user):
    if user.is_authenticated and user.role == user.Role.EMPLOYER:
        return True
    raise PermissionDenied

def is_candidate(user):
    if user.is_authenticated and user.role == user.Role.CANDIDATE:
        return True
    raise PermissionDenied


# for decorator calling
employer_required = user_passes_test(is_employer)
candidate_required = user_passes_test(is_candidate)