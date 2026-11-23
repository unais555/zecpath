from django.contrib import admin

from .models import (
    AIAnswer,
    AICallLog,
    AIInterviewSession,
    Application,
    CandidateReport,
    Job,
    NotificationLog,
    SavedJob,
)

admin.site.register(Job)
admin.site.register(Application)
admin.site.register(SavedJob)
admin.site.register(NotificationLog)
admin.site.register(AIAnswer)
admin.site.register(CandidateReport)
admin.site.register(AIInterviewSession)
admin.site.register(AICallLog)
