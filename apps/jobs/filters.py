import django_filters
from .models import Job

class JobFilter(django_filters.FilterSet):
    min_salary = django_filters.NumberFilter(field_name='min_salary', lookup_expr='gte')
    max_salary = django_filters.NumberFilter(field_name='max_salary', lookup_expr='lte')
    experience = django_filters.NumberFilter(field_name='experience', lookup_expr='lte')
    skills = django_filters.CharFilter(field_name='skills', lookup_expr='icontains')
    location = django_filters.CharFilter(field_name='location', lookup_expr='icontains')

    class Meta:
        model = Job
        fields = ['job_type', 'min_salary', 'max_salary', 'experience', 'skills', 'location']