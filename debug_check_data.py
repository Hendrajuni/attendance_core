
import os
import django
from datetime import date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_core.settings")
django.setup()

from attendance.models import Employee, EmployeeLeave, AttendanceLog

def check_angela():
    try:
        angela = Employee.objects.filter(full_name__icontains='Angela').first()
        if not angela:
            print("Angela not found")
            return

        print(f"Checking data for: {angela.full_name} (ID: {angela.id})")
        target_date = date(2026, 2, 9)
        
        # Check Leaves
        leaves = EmployeeLeave.objects.filter(
            employee=angela,
            start_date__lte=target_date,
            end_date__gte=target_date
        )
        print(f"Leaves found: {leaves.count()}")
        for l in leaves:
            print(f" - {l.leave_type} ({l.start_date} to {l.end_date})")

        # Check Logs
        logs = AttendanceLog.objects.filter(
            employee=angela,
            timestamp__date=target_date
        )
        print(f"Logs found: {logs.count()}")
        for log in logs:
            print(f" - {log.status} at {log.timestamp}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_angela()
