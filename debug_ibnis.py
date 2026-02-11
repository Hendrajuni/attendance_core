import os
import django
from datetime import date, datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import Employee, EmployeeLeave, AttendanceLog
from django.utils import timezone

def inspect_ibnis():
    try:
        # 1. Find IbniS
        emp = Employee.objects.filter(full_name__icontains='IbniS').first()
        if not emp:
            print("Employee 'IbniS' not found!")
            return

        print(f"Found Employee: {emp.full_name} (ID: {emp.id})")
        
        # 2. Check for Leaves
        print("\n--- Checking Leaves ---")
        leaves = EmployeeLeave.objects.filter(employee=emp).order_by('start_date')
        for l in leaves:
            print(f"Leave: {l.leave_type} ({l.start_date} to {l.end_date})")
            
        # 3. Check for Logs in Feb 2026
        print("\n--- Checking Logs (Feb 2026) ---")
        logs = AttendanceLog.objects.filter(
            employee=emp, 
            timestamp__year=2026, 
            timestamp__month=2
        ).order_by('timestamp')
        for log in logs:
            print(f"Log: {log.timestamp} - {log.status} (Source: {log.source_type})")
            
        # 4. Simulate Personal View Logic for Feb 2nd 2026
        target_date = date(2026, 2, 2)
        now_date = timezone.now().date()
        
        print(f"\n--- Simulation for {target_date} ---")
        print(f"Today: {now_date}")
        print(f"Is {target_date} < {now_date}? {target_date < now_date}")
        
        # Check Leave Query
        leave_query = EmployeeLeave.objects.filter(
            employee=emp,
            start_date__lte=target_date,
            end_date__gte=target_date
        ).first()
        print(f"Leave Query Result: {leave_query}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    inspect_ibnis()
