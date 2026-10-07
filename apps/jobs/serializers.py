from rest_framework import serializers
from .models import Job, Application

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