import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import AttendanceLog
from attendance.utils import determine_category
from django.utils import timezone

logs = AttendanceLog.objects.filter(
    source_type__in=['TELEGRAM', 'WHATSAPP'],
    timestamp__year=2026,
    timestamp__month=4
)

for log in logs:
    old_cat = log.log_category
    new_cat = determine_category(
        employee=log.employee,
        log_datetime=log.timestamp,
        source_type=log.source_type
    )[0]
    if old_cat != new_cat:
        log.log_category = new_cat
        log.save(update_fields=['log_category'])
        print(f"Fixed {log.employee.full_name} at {timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M')}: {old_cat} -> {new_cat}")

print("Done fixing historical log categories!")
