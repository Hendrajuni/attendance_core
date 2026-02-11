
import os
import django
from datetime import datetime, date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_core.settings")
django.setup()

from attendance.models import Employee, EmployeeLeave, AttendanceLog

def simulate_save():
    print("Simulating Save for Angela on 2026-02-09")
    employee = Employee.objects.filter(full_name__icontains='Angela').first()
    if not employee:
        print("Employee not found")
        return

    date_str = "2026-02-09"
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    action = "sakit"

    # 1. CLEAR EXISTING STATUS
    print(f"Clearing logs/leaves for {target_date}...")
    AttendanceLog.objects.filter(
        employee=employee,
        timestamp__date=target_date,
        source_type='FINGERPRINT',
        notes='Manual Entry'
    ).delete()
    
    existing_leaves = EmployeeLeave.objects.filter(
        employee=employee,
        start_date__lte=target_date,
        end_date__gte=target_date
    )
    count = existing_leaves.count()
    print(f"Found {count} existing leaves to delete.")
    existing_leaves.delete() 

    # 2. APPLY NEW ACTION
    print(f"Applying action: {action}")
    if action in ['izin', 'sakit', 'cuti']:
        leave_type_map = {'izin': 'IZIN', 'sakit': 'SAKIT', 'cuti': 'CUTI'}
        l_type = leave_type_map.get(action, 'IZIN')
        
        try:
            leave = EmployeeLeave.objects.create(
                employee=employee,
                leave_type=l_type,
                start_date=target_date,
                end_date=target_date,
                notes='Manual Update via Matrix'
            )
            print(f"Created Leave: {leave} (ID: {leave.id})")
        except Exception as e:
            print(f"FAILED to create leave: {e}")

    # Verify
    print("Verifying...")
    final_leaves = EmployeeLeave.objects.filter(
         employee=employee,
         start_date__lte=target_date,
         end_date__gte=target_date
    )
    print(f"Final Count: {final_leaves.count()}")
    for l in final_leaves:
        print(f" - {l.leave_type} ({l.start_date} to {l.end_date})")

    # Verify Stats Helper
    print("\nVerifying Stats Helper...")
    try:
        from portal.views import get_employee_monthly_stats
        stats = get_employee_monthly_stats(employee, target_date.year, target_date.month)
        print(f"Stats for {target_date.strftime('%B %Y')}: {stats}")
    except Exception as e:
        print(f"Stats Helper Failed: {e}")


if __name__ == "__main__":
    simulate_save()
