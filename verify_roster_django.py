import os
import django

# Setup Django FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

# Now import Django stuff
from django.test import Client
from django.contrib.auth.models import User
from attendance.models import Employee, DailySchedule, DailyShiftAssignment

def verify():
    # 1. Setup Data
    emp = Employee.objects.filter(is_shift_worker=True).first()
    if not emp:
        print("FAIL: No Shift Worker found.")
        return
    
    target_date = "2024-01-01"
    
    # Ensure User exists for login
    user, created = User.objects.get_or_create(username='admin')
    if created:
        user.set_password('password123')
        user.save()
    
    # 2. Login
    # Use HTTP_HOST='localhost' to avoid DisallowedHost
    c = Client(HTTP_HOST='localhost')
    c.force_login(user)
    print("Logged in as admin.")

    # 3. Request Modal (FP Edit Cell)
    edit_url = f"/portal/fp/edit-cell/{emp.id}/{target_date}/"
    print(f"GET {edit_url}")
    r = c.get(edit_url)
    
    if r.status_code != 200:
        print(f"FAIL: Modal GET status {r.status_code}")
        # print(r.content.decode())
        return

    content = r.content.decode()
    if "Atur Shift" in content:
        print("SUCCESS: 'Atur Shift' tab found.")
    else:
        print("FAIL: 'Atur Shift' tab NOT found.")
        # print(content) # Debug

    # 4. Save Roster
    shift = DailySchedule.objects.filter(code='SHIFT-MALAM').first()
    if not shift:
        print("FAIL: SHIFT-MALAM not found")
        return

    save_url = "/portal/attendance/save-roster/"
    post_data = {
        'employee_id': emp.id,
        'date_str': target_date,
        'shift_id': shift.id
    }
    
    # Emulate HTMX
    print(f"POST {save_url} with Shift {shift.code}")
    r = c.post(save_url, post_data, headers={'HX-Request': 'true'})
    
    if r.status_code == 200 and r.has_header('HX-Refresh'):
        print("SUCCESS: Response 200 + HX-Refresh.")
    else:
        print(f"FAIL: Status {r.status_code}")
        print(r.headers)
        # print(r.content.decode())

    # 5. Verify DB
    assignment = DailyShiftAssignment.objects.filter(employee=emp, date=target_date).first()
    if assignment and assignment.shift == shift:
        print(f"SUCCESS: Database updated. Shift: {assignment.shift.code}")
    else:
        print("FAIL: Database not updated.")

if __name__ == '__main__':
    verify()
