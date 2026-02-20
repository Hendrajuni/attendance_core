import requests
import os
import django
# from bs4 import BeautifulSoup # Removed

# Setup Django to get models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import Employee, DailySchedule, DailyShiftAssignment

BASE_URL = "http://localhost:8000"
LOGIN_URL = f"{BASE_URL}/login/"
SAVE_ROSTER_URL = f"{BASE_URL}/portal/attendance/save-roster/"

def verify():
    # 1. Get Shift Worker and Date
    emp = Employee.objects.filter(is_shift_worker=True).first()
    if not emp:
        print("FAIL: No Shift Worker found.")
        return
    
    target_date = "2024-01-01" # Arbitrary date
    edit_url = f"{BASE_URL}/portal/attendance/edit/{emp.id}/{target_date}/"
    
    print(f"Testing for Employee: {emp.full_name}, Date: {target_date}")

    # 2. Login
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    # Get CSRF
    try:
        r = session.get(LOGIN_URL)
        if 'csrftoken' in session.cookies:
            csrftoken = session.cookies['csrftoken']
        else:
            print("FAIL: No CSRF token in cookies")
            return
    except Exception as e:
        print(f"FAIL: Logic Error {e}")
        return
    
    login_data = {
        'username': 'admin',
        'password': 'password123',
        'csrfmiddlewaretoken': csrftoken
    }
    r = session.post(LOGIN_URL, data=login_data, headers={'Referer': LOGIN_URL})
    
    # Check if login successful (redirect to / or /portal/ or dashboard)
    # Simple check: response shouldn't contain "Sign In" form
    if "Sign In" in r.text and "csrfmiddlewaretoken" in r.text:
         print("FAIL: Login failed (Still on login page)")
         return
    print("Login simulated.")

    # 3. Fetch Modal
    r = session.get(edit_url)
    if r.status_code != 200:
        print(f"FAIL: Fetch Modal status {r.status_code}")
        # print(r.text)
        return
    
    # Check for Tabs
    if "Atur Shift" in r.text:
        print("SUCCESS: 'Atur Shift' tab found in modal HTML.")
    else:
        print("FAIL: 'Atur Shift' tab NOT found in modal HTML.")
        # print(r.text) # Debug

    # 4. Save Roster
    # Find a shift
    shift = DailySchedule.objects.filter(code='SHIFT-MALAM').first()
    if not shift:
        print("FAIL: SHIFT-MALAM not found")
        return

    post_data = {
        'employee_id': emp.id,
        'date_str': target_date,
        'shift_id': shift.id,
        'csrfmiddlewaretoken': session.cookies['csrftoken']
    }
    
    headers = {
        'HX-Request': 'true',
        'Referer': edit_url
    }
    
    r = session.post(SAVE_ROSTER_URL, data=post_data, headers=headers)
    
    if r.status_code == 200 and 'HX-Refresh' in r.headers:
        print("SUCCESS: Save Roster returned 200 and HX-Refresh header.")
    else:
        print(f"FAIL: Save Roster returned path: {r.request.url} status: {r.status_code}")
        print(f"Headers: {r.headers}")
        # print(r.text)

    # 5. Verify DB
    assignment = DailyShiftAssignment.objects.filter(employee=emp, date=target_date).first()
    if assignment and assignment.shift == shift:
        print(f"SUCCESS: Database updated correctly. Shift is {assignment.shift.code}")
    else:
        print("FAIL: Database not updated.")

if __name__ == '__main__':
    verify()
