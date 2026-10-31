from django.db import transaction
from django.utils import timezone
from apps.jobs.models import AvailabilitySlot, InterviewSchedule
from apps.jobs.tasks import send_async_email # Reusing your Celery task from Day 32

class SchedulingEngine:
    
    @staticmethod
    def get_available_slots(employer_id):
        """Fetches future unbooked slots for a specific employer."""
        now = timezone.localtime(timezone.now())
        return AvailabilitySlot.objects.filter(
            employer_id=employer_id, 
            start_time__gt=now, 
            is_booked=False
        ).order_by('start_time')

    @staticmethod
    def book_slot(application, slot_id):
        """Books a slot with strict transaction locking to prevent double-booking."""
        with transaction.atomic():
            # select_for_update() locks this specific database row until the transaction finishes.
            # If Candidate B tries to book it, their request waits until Candidate A is done.
            try:
                slot = AvailabilitySlot.objects.select_for_update(nowait=True).get(id=slot_id)
            except AvailabilitySlot.DoesNotExist:
                raise ValueError("Slot does not exist.")
            except Exception: # Catches database lock errors
                raise ValueError("This slot is currently being booked by someone else.")
            
            if slot.is_booked:
                raise ValueError("This slot is already booked. Please choose another.")
            
            # 1. Update Slot Status
            slot.is_booked = True
            slot.save()

            # 2. Rescheduling Logic vs New Booking
            if hasattr(application, 'interview_schedule'):
                schedule = application.interview_schedule
                
                # Free up the old slot
                if schedule.slot:
                    old_slot = schedule.slot
                    old_slot.is_booked = False
                    old_slot.save()
                
                schedule.slot = slot
                schedule.status = InterviewSchedule.ScheduleStatus.RESCHEDULED
                schedule.save()
                event_type = 'INTERVIEW_RESCHEDULED'
            else:
                schedule = InterviewSchedule.objects.create(
                    application=application,
                    slot=slot,
                    status=InterviewSchedule.ScheduleStatus.SCHEDULED
                )
                event_type = 'INTERVIEW_SCHEDULED'

            # 3. Notification Triggers (Celery Async Email)
            SchedulingEngine._trigger_calendar_email(schedule, event_type)
            
            return schedule

    @staticmethod
    def _trigger_calendar_email(schedule, event_type):
        """Prepares context and fires the Celery background task."""
        candidate_email = schedule.application.candidate.user.email
        job_title = schedule.application.job.title
        formatted_time = schedule.slot.start_time.strftime('%A, %B %d, %Y at %I:%M %p')

        context = {
            'candidate_email': candidate_email,
            'job_title': job_title,
            'start_time': formatted_time,
            'status': schedule.status
        }
        
        subject = f"Interview {schedule.status}: {job_title}"
        
        # Drops the email job into Redis instantly
        send_async_email.delay(
            recipient_email=candidate_email,
            subject=subject,
            template_name='interview_confirmation', # Assumes this template exists in your emails folder
            context=context,
            event_type=event_type
        )