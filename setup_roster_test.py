import os
import django
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import Employee, DailySchedule

def setup_data():
    # 1. Ensure Daily Schedules exist
    schedules = [
        ('SHIFT-PAGI', '07:00', '15:00'),
        ('SHIFT-SIANG', '15:00', '23:00'),
        ('SHIFT-MALAM', '23:00', '07:00'),
        ('OFF', '00:00', '00:00'),
    ]
    
    for name, cin, cout in schedules:
        obj, created = DailySchedule.objects.get_or_create(
            code=name,
            defaults={
                'name': name,
                'clock_in': cin,
                'clock_out': cout
            }
        )
        if created:
            print(f"Created Schedule: {name}")
        else:
            print(f"Schedule Exists: {name}")

    # 2. Set an Employee as Shift Worker
    # Try to find one, or create dummy
    emp = Employee.objects.filter(is_active=True).first()
    if emp:
        emp.is_shift_worker = True
        emp.save()
        print(f"Updated Employee {emp.full_name} ({emp.nik}) as Shift Worker")
    else:
        print("No active employee found to update.")

if __name__ == '__main__':
    setup_data()
