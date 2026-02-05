from django.core.management.base import BaseCommand
from django.db import transaction
from zk import ZK
from attendance.models import FingerprintDevice, Employee
import random

class Command(BaseCommand):
    help = 'Import employee data (ID & Name) from fingerprint devices'

    def add_arguments(self, parser):
        parser.add_argument(
            '--device_ip',
            type=str,
            help='Specific Device IP Address to import from',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Import from ALL active devices',
        )

    def handle(self, *args, **kwargs):
        target_ip = kwargs.get('device_ip')
        import_all = kwargs.get('all')

        if not target_ip and not import_all:
            self.stdout.write(self.style.ERROR("Error: You must specify either --device_ip <IP> or --all"))
            return

        devices = FingerprintDevice.objects.filter(is_active=True)
        
        if target_ip:
            devices = devices.filter(ip_address=target_ip)
            if not devices.exists():
                self.stdout.write(self.style.ERROR(f"No active device found with IP {target_ip}"))
                return

        self.stdout.write(f"Starting import from {devices.count()} devices...")

        for device in devices:
            self.stdout.write(f"Connecting to {device.name} ({device.ip_address})...")
            
            zk = ZK(device.ip_address, port=device.port, timeout=10)
            conn = None
            try:
                conn = zk.connect()
                users = conn.get_users()
                self.stdout.write(f"  > Found {len(users)} users in device.")

                created_count = 0
                updated_count = 0
                
                with transaction.atomic():
                    for user in users:
                        user_id = int(user.user_id)
                        name = user.name.strip() if user.name else f"No Name ({user_id})"
                        
                        # Check if employee exists
                        employee = Employee.objects.filter(device_user_id=user_id).first()

                        if not employee:
                            # Create new employee
                            temp_nik = f"TEMP-{user_id}"
                            
                            # Ensure unique NIK
                            while Employee.objects.filter(nik=temp_nik).exists():
                                temp_nik = f"TEMP-{user_id}-{random.randint(100,999)}"

                            Employee.objects.create(
                                nik=temp_nik,
                                full_name=name,
                                device_user_id=user_id,
                                home_base=device.location, # Smart assign location
                                is_active=True
                            )
                            self.stdout.write(f"    + Created: {name} (ID: {user_id}) -> Loc: {device.location.name}")
                            created_count += 1
                        else:
                            # Update Existing User
                            updated_fields = []
                            
                            # Update name if changed
                            if employee.full_name != name:
                                employee.full_name = name
                                updated_fields.append("Name")
                            
                            # Update home_base ONLY if not set (don't overwrite admin manual changes)
                            if not employee.home_base:
                                employee.home_base = device.location
                                updated_fields.append("HomeBase")

                            if updated_fields:
                                employee.save()
                                self.stdout.write(f"    . Updated {employee.full_name}: {', '.join(updated_fields)}")
                                updated_count += 1

                self.stdout.write(self.style.SUCCESS(f"  > Finished {device.name}. Created: {created_count}, Updated: {updated_count}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  > Failed {device.name}: {str(e)}"))
            finally:
                if conn:
                    conn.disconnect()

        self.stdout.write(self.style.SUCCESS("---------------------------------------------------"))
        self.stdout.write(self.style.SUCCESS("Import process completed."))
