from django.core.management.base import BaseCommand
from apps.jobs.models import Application
from apps.jobs.automation_engine import process_application_automation

class Command(BaseCommand):
    help = 'Runs ATS auto-shortlisting and auto-rejection batch processing.'

    def handle(self, *args, **kwargs):
        pending_apps = Application.objects.filter(
            status=Application.ApplicationStatus.APPLIED,
            is_manually_overridden=False,
            job__is_automation_enabled=True
        )
        # print(pending_apps)
        count = 0
        for app in pending_apps:
            process_application_automation(app.id)
            count +=1

        self.stdout.write(self.style.SUCCESS(f'Batch processing complete. Evaluated {count} applications.'))