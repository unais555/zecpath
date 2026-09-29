from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CandidateProfile, EmployerProfile

User = get_user_model()

class UserRegistrationSerializers(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ["email", "phone", "password", "role"]

    def create(self, validated_data):
        user= User.objects.create_user(
            email = validated_data['email'],
            phone = validated_data.get('phone', ''),
            password = validated_data["password"],
            role = validated_data['role']
        )
        return user

class CandidateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateProfile
        fields = ['id', 'skills', 'education', 'experience', 'expected_salary']
        

class EmployerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployerProfile
        fields = ['id', 'company_name', 'domain', 'size', 'is_verified']
        read_only_fields = ['is_verified']