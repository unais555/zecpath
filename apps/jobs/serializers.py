from rest_framework import serializers
from .models import Job, Application, ApplicationLog


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = '__all__'
        read_only_fields = ['id', 'employer', 'created_at', 'updated_at']

    def validate(self, data):
        min_salary = data.get('min_salary', self.instance.min_salary if self.instance else None)
        max_salary = data.get('max_salary', self.instance.max_salary if self.instance else None)
        if min_salary and max_salary and min_salary > max_salary:
            raise serializers.ValidationError({"max_salary" : "Maximum salary cannot be less than minimum salary."})
        return data

class ApplicationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='job.employer.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Application
        fields = ['id', 'job', 'job_title', 'company_name', 'resume_snapshot', 'status', 'status_display', 'applied_at']



class ApplicationStatusUpdateSerializer(serializers.ModelSerializer):
    notes = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Application
        fields = ['status', 'notes']

    def validate_status(self, new_status):
        current_status = self.instance.status
        

        allowed_transitions = {
            'applied': ['shortlisted', 'rejected'],
            'shortlisted': ['interview_scheduled', 'rejected'],
            'interview_scheduled': ['selected', 'rejected'],
            'selected': [],
            'rejected': [], 
        }

        if new_status not in allowed_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Invalid transition. Cannot move application from '{current_status}' to '{new_status}'."
            )
        
        return new_status

class EmployerApplicantSerializer(serializers.ModelSerializer):
    candidate_email = serializers.EmailField(source='candidate.user.email', read_only=True)
    candidate_skills = serializers.CharField(source='candidate.skills', read_only=True)
    candidate_experience = serializers.IntegerField(source='candidate.experience', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'job_title', 'candidate_email', 'candidate_skills', 
            'candidate_experience', 'resume_snapshot', 'status', 'applied_at'
        ]