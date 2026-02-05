import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from zk import ZK, const
from attendance.models import FingerprintDevice, Employee, AttendanceLog
from attendance.utils import determine_category

class Command(BaseCommand):
    help = 'Synchronize attendance data from all active fingerprint devices'

    def handle(self, *args, **kwargs):
        devices = FingerprintDevice.objects.filter(is_active=True)
        
        self.stdout.write(f"Found {devices.count()} active devices.")

        for device in devices:
            self.stdout.write(f"Connecting to {device.name} ({device.ip_address}:{device.port})...")
            
            zk = ZK(device.ip_address, port=device.port, timeout=5)
            conn = None
            try:
                conn = zk.connect()
                # Disable device to prevent new logs while reading (optional, depends on traffic)
                conn.disable_device() 
                
                attendance_list = conn.get_attendance()
                self.stdout.write(f"  > Retrieved {len(attendance_list)} records from device.")

                new_records_count = 0
                for att in attendance_list:
                    user_id = int(att.user_id)
                    timestamp = att.timestamp # This is naive datetime from device

                    # Make timestamp aware if project uses timezone support
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)

                    # Find employee
                    try:
                        employee = Employee.objects.get(device_user_id=user_id, is_active=True)
                    except Employee.DoesNotExist:
                        # self.stdout.write(self.style.WARNING(f"  > Unknown User ID {user_id}. Skipping."))
                        continue

                    # Determine verification method (Simplified)
                    ver_method = 'FINGER' # Default
                    # You might need to map att.status/att.punch to your choices if ZK supports it details

                    # Determine time category using shared utility function
                    category = determine_category(timestamp)

                    # Save to AttendanceLog
                    # We use get_or_create to avoid duplicates for the same employee at the exact same second
                    log, created = AttendanceLog.objects.get_or_create(
                        employee=employee,
                        timestamp=timestamp,
                        defaults={
                            'status': 'HADIR',
                            'source_type': 'FINGERPRINT',
                            'captured_at': device.location,
                            'verification_method': ver_method,
                            'log_category': category,  # Standardized time slot
                        }
                    )

                    if created:
                        new_records_count += 1
                
                self.stdout.write(self.style.SUCCESS(f"  > Successfully synced. New records: {new_records_count}"))
                
                # Re-enable device
                conn.enable_device()

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  > Failed to connect/sync with {device.name}: {str(e)}"))
            finally:
                if conn:
                    conn.disconnect()
        
        self.stdout.write(self.style.SUCCESS("Sync process completed for all devices."))
