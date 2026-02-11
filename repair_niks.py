
import os
import django
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_core.settings')
django.setup()

from attendance.models import Employee, FingerprintDevice

def fix_niks():
    with open('repair_log.txt', 'w') as f:
        f.write("Starting NIK fix script...\n")
        
        # Find employees with the old temporary format
        # Also check if NIK starts with 'T.' regardless of case
        emps = Employee.objects.filter(nik__startswith='T.', is_verified=False)
        f.write(f"Found {emps.count()} employees with 'T.' prefix to fix.\n")
        
        count = 0
        for emp in emps:
            f.write(f"Processing {emp.nik}...\n")
            parts = emp.nik.split('.')
            
            if len(parts) == 3:
                short_uuid = parts[1]
                user_id = parts[2]
                
                f.write(f"  - Short UUID: {short_uuid}\n")
                f.write(f"  - User ID: {user_id}\n")
                
                # Find device ending with this short_uuid
                target_device = None
                for d in FingerprintDevice.objects.all():
                    # Check both string representation of ID and if ID is UUID
                    str_id = str(d.id)
                    if str_id.endswith(short_uuid):
                        target_device = d
                        break
                
                # Use last 6 chars of device ID to ensure we have space for user_id
                if target_device: # Only proceed if a target device was found
                    # Use last 6 chars of device ID to ensure we have space for user_id
                    # FG-{short_uuid}-{user_id}
                    # FG-a705bb-4510 (3+7+4 = 14 chars)
                    short_dev_id = str(target_device.id)[-6:]
                    new_nik = f"FG-{short_dev_id}-{user_id}"
                    if len(new_nik) > 20:
                        new_nik = new_nik[:20]
                    
                    f.write(f"  - Renaming {emp.nik} -> {new_nik}\n")
                    emp.nik = new_nik
                    emp.save()
                    count += 1
                else:
                    f.write(f"  - Could not find device ending with '{short_uuid}'\n")
            else:
                f.write(f"  - Skipping malformed NIK: {emp.nik}\n")

        f.write(f"Fixed {count} NIKs.\n")

if __name__ == '__main__':
    fix_niks()
