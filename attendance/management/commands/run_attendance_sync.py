from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import AttendanceMachine

class Command(BaseCommand):
    help = 'Runs automated attendance sync for machines scheduled at the current time.'

    def handle(self, *args, **options):
        now = timezone.localtime(timezone.now())
        current_time = now.strftime('%H:%M')
        
        self.stdout.write(f"[{now}] Checking for scheduled syncs at {current_time}...")
        
        # Filter machines that are active and scheduled for this minute
        machines = AttendanceMachine.objects.filter(
            is_active=True,
            auto_sync_time=current_time
        )
        
        if not machines.exists():
            self.stdout.write("No machines scheduled for sync right now.")
            return

        for machine in machines:
            self.stdout.write(f"Syncing {machine.name} ({machine.ip_address})...")
            try:
                status, msg, records = machine.perform_sync()
                self.stdout.write(self.style.SUCCESS(f"  -> {status}: {msg} ({records} records)"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  -> ERROR: {str(e)}"))
