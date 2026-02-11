import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import Employee, EmployeeShiftAssignment, AttendanceLog
from attendance.utils import get_employee_schedule
from django.utils import timezone

def inspect_adi():
    try:
        # 1. Get Employee
        try:
            adi = Employee.objects.get(id='2e57eacf-cfdc-4af7-91cd-e638bb56f127')
        except:
             adi = Employee.objects.filter(full_name__icontains='Adi Witono').first()
        
        print(f"Inspecting Employee: {adi.full_name} ({adi.nik}) ID: {adi.id}")
        
        # Check logs for Feb 02
        d = date(2026, 2, 2)
        print(f"Logs for {d}:")
        logs = AttendanceLog.objects.filter(
            employee=adi,
            timestamp__year=d.year,
            timestamp__month=d.month,
            timestamp__day=d.day
        ).order_by('timestamp')
        
        for log in logs:
            local_dt = timezone.localtime(log.timestamp)
            print(f" - {local_dt.time()} | Cat: {log.log_category} | Status: {log.status}")

    except Employee.DoesNotExist:
        print("Error: Employee 'Adi Witono' not found.")

if __name__ == '__main__':
    inspect_adi()
