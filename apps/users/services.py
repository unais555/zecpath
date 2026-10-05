from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

def create_user_account(email: str, password:str, role: str, phone:str =""):
    with transaction.atomic():
        User.objects.create_user(
            email=email,
            password=password,
            role=role,
            phone=phone
        )
    return User

def deactivate_user_account(user):
    user.is_active = False
    user.save(update_fields=['is_active'])