import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import AttendanceLog, Employee

# Get Alby
try:
    emp = Employee.objects.filter(full_name__icontains="Alby").first()
    if emp:
        logs = AttendanceLog.objects.filter(
            employee=emp, 
            timestamp__year=2026, 
            timestamp__month=3, 
            timestamp__day=3
        ).order_by('timestamp')
        
        print(f"--- LOGS FOR {emp.full_name} ON 2026-03-03 ---")
        for log in logs:
            print(f"Time: {log.timestamp.strftime('%H:%M:%S')}, Source: {log.source_type}, "
                  f"Device: {log.device_id}, Excused: {log.is_excused}, Reason: {log.excuse_reason}, Notes: {log.notes}")
    else:
        print("Employee not found.")
except Exception as e:
    print(f"Error: {e}")
