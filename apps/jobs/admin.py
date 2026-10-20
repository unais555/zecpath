from django.contrib import admin
from .models import Job, Application, SavedJob, NotificationLog

admin.site.register(Job)
admin.site.register(Application)
admin.site.register(SavedJob)
admin.site.register(NotificationLog)

