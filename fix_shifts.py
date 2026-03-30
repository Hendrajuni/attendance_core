import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import EmployeeShiftAssignment
from datetime import date

updated = 0
assignments = EmployeeShiftAssignment.objects.filter(is_active=True)
for a in assignments:
    start_date = a.employee.joined_date if a.employee.joined_date else date(2000, 1, 1)
    if a.effective_from != start_date:
        a.effective_from = start_date
        a.save()
        updated += 1
print(f'Fixed {updated} active assignments.')
