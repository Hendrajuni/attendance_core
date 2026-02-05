import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from zk import ZK, const
from attendance.models import FingerprintDevice, Employee, AttendanceLog
from attendance.utils import determine_category


class Command(BaseCommand):
    help = 'Synchronize attendance data from all active fingerprint devices'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each log',
        )
        parser.add_argument(
            '--ip',
            type=str,
            help='Sync only specific device by IP address',
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Sync only logs for specific date (YYYY-MM-DD)',
        )

    def handle(self, *args, **kwargs):
        verbose = kwargs.get('verbose', False)
        target_ip = kwargs.get('ip')
        target_date_str = kwargs.get('date')
        
        target_date = None
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR("Invalid date format. Use YYYY-MM-DD"))
                return

        devices = FingerprintDevice.objects.filter(is_active=True)
        if target_ip:
            devices = devices.filter(ip_address=target_ip)
        
        if not devices.exists():
            self.stdout.write(self.style.WARNING(f"No active devices found{' for IP ' + target_ip if target_ip else ''}."))
            return
            
        self.stdout.write(f"Found {devices.count()} active devices.")

        for device in devices:
            self.stdout.write(f"Connecting to {device.name} ({device.ip_address}:{device.port})...")
            
            zk = ZK(device.ip_address, port=device.port, timeout=10)
            conn = None
            try:
                conn = zk.connect()
                # Disable device to prevent new logs while reading (optional)
                conn.disable_device() 
                
                attendance_list = conn.get_attendance()
                if not attendance_list:
                     self.stdout.write("  > No records found on device.")
                     conn.enable_device()
                     continue

                self.stdout.write(f"  > Retrieved {len(attendance_list)} records from device.")

                new_records_count = 0
                skipped_count = 0
                unknown_user_count = 0
                date_filtered_count = 0

                for att in attendance_list:
                    user_id = int(att.user_id)
                    timestamp = att.timestamp  # Naive datetime from device

                    # Filter by date if requested
                    if target_date and timestamp.date() != target_date:
                        date_filtered_count += 1
                        continue

                    # Make timestamp aware
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)

                    # Find employee
                    try:
                        employee = Employee.objects.get(device_user_id=user_id, is_active=True)
                    except Employee.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"  ? Unknown User ID: {user_id}")) # Debug print
                        unknown_user_count += 1
                        continue

                    # Determine verification method
                    ver_method = 'FINGER'

                    # Determine time category using THE BRAIN
                    category, schedule_name = determine_category(employee, timestamp)

                    # Save to AttendanceLog
                    log, created = AttendanceLog.objects.get_or_create(
                        employee=employee,
                        timestamp=timestamp,
                        defaults={
                            'status': 'HADIR',
                            'source_type': 'FINGERPRINT',
                            'captured_at': device.location,
                            'verification_method': ver_method,
                            'log_category': category,
                        }
                    )

                    if created:
                        new_records_count += 1
                        if verbose:
                            time_str = timestamp.strftime('%H:%M')
                            shift_info = f" (Shift: {schedule_name})" if schedule_name else " (No Shift)"
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ {employee.full_name}: {time_str} -> {category}{shift_info}"
                                )
                            )
                    else:
                        skipped_count += 1
                
                msg = f"  > Synced: {new_records_count} new, {skipped_count} duplicates"
                if unknown_user_count:
                    msg += f", {unknown_user_count} unknown users"
                if date_filtered_count:
                    msg += f", {date_filtered_count} skipped (other dates)"
                
                self.stdout.write(self.style.SUCCESS(msg))
                
                # Re-enable device
                conn.enable_device()

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  > Failed to connect/sync with {device.name}: {str(e)}"))
            finally:
                if conn:
                    conn.disconnect()
        
        self.stdout.write(self.style.SUCCESS("Sync process completed."))

