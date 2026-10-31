import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zecpath.settings')
app = Celery('zecpath')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# Configure Celery Beat to run the reminder scanner every 15 minutes
app.conf.beat_schedule = {
    'scan-interview-reminders-every-15-mins': {
        'task': 'apps.jobs.tasks.process_interview_reminders',
        'schedule': crontab(minute='*/15'), # Runs at :00, :15, :30, :45
    },
}