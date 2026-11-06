from django.db.models import Count, Q
from django.core.cache import cache
from apps.jobs.models import Job, Application

class AnalyticsService:
    @staticmethod
    def get_job_funnel_metrics(job_id, employer_user_id):
        #Performance Optimization: Check Cache First
        cache_key = f"analytics_job_{job_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        metrics = Application.objects.filter(
            job_id=job_id,
            job__employer__user=employer_user_id
        ).aggregate(
            total_applied=Count('id'),
            shortlisted=Count('id', filter=Q(status='SHORTLISTED')),
            interviewed=Count('id', filter=Q(status='INTERVIEW_SCHEDULED')),
            selected=Count('id', filter=Q(status='SELECTED'))
        )

        total = metrics['total_applied'] or 0

        data = {
            "job_id": job_id,
            "funnel": {
                "applied": total,
                "shortlisted": metrics['shortlisted'],
                "interviewed": metrics['interviewed'],
                "selected": metrics['selected']
            },
            "conversion_rates": {
                "apply_to_shortlist": round((metrics['shortlisted'] / total * 100), 1) if total else 0,
                "shortlist_to_interview": round((metrics['interviewed'] / metrics['shortlisted'] * 100), 1) if metrics['shortlisted'] else 0,
                "interview_to_hire": round((metrics['selected'] / metrics['interviewed'] * 100), 1) if metrics['interviewed'] else 0,
            }
        }

        # 4. Save to Redis for 15 minutes (900 seconds)
        cache.set(cache_key, data, timeout=900)
        
        return data