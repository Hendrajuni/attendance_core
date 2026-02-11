import os
import django
from datetime import date, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_core.settings")
django.setup()

from attendance.models import Employee, AttendanceLog, EmployeeLeave

def inspect_ibni():
    # Search for 51010
    print("\n--- Searching for '51010' ---")
    e1 = Employee.objects.filter(device_user_id='51010').first()
    if e1: print(f"Found by Device ID: {e1.full_name}")
    
    e2 = Employee.objects.filter(nik__icontains='51010').first()
    if e2: print(f"Found by NIK: {e2.full_name}")

    # Check Leaves for "51010" in notes
    l1 = EmployeeLeave.objects.filter(notes__icontains='51010').first()
    if l1: print(f"Found Leave with '51010' in notes: {l1.employee.full_name} - {l1.notes}")

    target_emp = e1 or e2
    if target_emp:
        print(f"Inspecting found employee: {target_emp.full_name}")
        year = 2026
        month = 2
        
        # Check Leaves
        leaves = EmployeeLeave.objects.filter(
            employee=target_emp,
            start_date__year=year,
            start_date__month=month
        )
        
        for l in leaves:
            print(f"Leaf found: {l.leave_type} ({l.start_date} to {l.end_date}) ID: {l.id} Notes: {l.notes}")
    else:
        print("No employee or log found with identifier '51010'")

if __name__ == "__main__":
    inspect_ibni()
