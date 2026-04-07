import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import AttendanceLog
count = AttendanceLog.objects.count()
print("TOTAL LOGS:", count)
if count > 0:
    print("Latest:", AttendanceLog.objects.order_by('-timestamp').first().timestamp)
