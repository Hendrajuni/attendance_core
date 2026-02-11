import os
import django
from datetime import date, datetime, timedelta, time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import Employee
from attendance.utils import get_employee_schedule
from django.utils import timezone

def debug_logic():
    # 1. Setup
    try:
        emp = Employee.objects.get(id='2e57eacf-cfdc-4af7-91cd-e638bb56f127') # Adi Witono
    except:
        emp = Employee.objects.filter(full_name__icontains='Adi Witono').first()
        
    d = date(2026, 2, 2) # Feb 02
    cin_time_str = '08:18'
    cin_time = datetime.strptime(cin_time_str, '%H:%M').time()
    
    # 2. Get Schedule
    daily_sch, shift_pattern = get_employee_schedule(emp, d)
    
    # 3. Logic from views.py
    dummy_date = date(2000, 1, 1)
    DEFAULT_SCHEDULE_IN = datetime.strptime('08:00', '%H:%M').time()
    
    sch_in = DEFAULT_SCHEDULE_IN
    tol = 0
    
    if daily_sch:
        print(f"Schedule Found: {shift_pattern.name}")
        sch_in = daily_sch.clock_in
        tol = daily_sch.late_tolerance
    else:
        print("No Schedule Found")
        
    # Threshold
    dt_sch = datetime.combine(dummy_date, sch_in)
    dt_threshold = dt_sch + timedelta(minutes=tol)
    
    print(f"Date: {d}")
    print(f"In: {cin_time}")
    print(f"Sch In: {sch_in}")
    print(f"Tol: {tol}")
    print(f"Threshold: {dt_threshold.time()}")
    
    # Check Late
    # Assuming NOT holiday/weekend for now to check pure calc
    is_holiday = False
    is_weekend = False
    
    if cin_time > dt_threshold.time() and not is_holiday and not is_weekend:
        dt_in = datetime.combine(dummy_date, cin_time)
        diff = (dt_in - dt_threshold).total_seconds() / 60
        late_minutes = int(diff)
        print(f"RESULT: LATE {late_minutes} minutes")
    else:
        print("RESULT: NOT LATE")

if __name__ == '__main__':
    debug_logic()
