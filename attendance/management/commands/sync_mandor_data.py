import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from attendance.models import Employee, WorkLocation

class Command(BaseCommand):
    help = 'Sync Mandor/Employee Telegram IDs from Google Sheet CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            required=True,
            help='URL of the CSV file (Published Google Sheet)',
        )
        parser.add_argument(
            '--location',
            type=str,
            required=False,
            help='Code of WorkLocation to assign for new employees (e.g. KBN-A)',
        )

    def handle(self, *args, **kwargs):
        url = kwargs['url']
        location_code = kwargs.get('location')
        
        self.stdout.write(f"Reading data from {url}...")

        try:
            df = pd.read_csv(url)
            # Normalize column names just in case
            df.columns = [c.strip().upper() for c in df.columns]
            
            # Check required columns
            required_cols = ['NAMA PEGAWAI', 'TELE USERID']
            if not all(col in df.columns for col in required_cols):
                self.stdout.write(self.style.ERROR(f"CSV missing required columns: {required_cols}. Found: {list(df.columns)}"))
                return

            updated_count = 0
            created_count = 0
            not_found_count = 0

            with transaction.atomic():
                for index, row in df.iterrows():
                    raw_name = str(row['NAMA PEGAWAI'])
                    tele_id = str(row['TELE USERID']).strip()

                    # Simple validation
                    if not raw_name or not tele_id or tele_id.lower() == 'nan':
                        continue

                    # 1. CLEAN NAME
                    # Remove " | PROGRAMMER" etc
                    clean_name = raw_name.split('|')[0].strip()
                    
                    # Remove extra spaces
                    clean_name = " ".join(clean_name.split())

                    # 2. SEARCH STRATEGY
                    employees = Employee.objects.none()
                    match_method = "Exact/Contain"

                    # Attempt A: Search by Clean Name
                    employees = Employee.objects.filter(full_name__icontains=clean_name, is_active=True)

                    # Attempt B: Search by First 2 Words (if A failed)
                    if not employees.exists():
                        parts = clean_name.split()
                        if len(parts) >= 2:
                            term = f"{parts[0]} {parts[1]}"
                            employees = Employee.objects.filter(full_name__icontains=term, is_active=True)
                            match_method = f"Fuzzy (2 words: {term})"
                        elif len(parts) == 1:
                            term = parts[0]
                            # Only search if term length > 2 to avoid matching "M" to everyone
                            if len(term) > 2:
                                employees = Employee.objects.filter(full_name__icontains=term, is_active=True)
                                match_method = f"Fuzzy (1 word: {term})"

                    # 3. UPDATE
                    if employees.exists():
                        # If multiple found, warning inside log
                        if employees.count() > 1:
                            self.stdout.write(self.style.WARNING(f"  ? Ambiguous: '{clean_name}' matches {employees.count()} people. Using first."))
                        
                        employee = employees.first()
                        
                        if employee.telegram_user_id != tele_id:
                            employee.telegram_user_id = tele_id
                            employee.save()
                            self.stdout.write(f"  > Updated [{match_method}]: {clean_name} -> {employee.full_name} (ID: {tele_id})")
                            updated_count += 1
                        else:
                            # self.stdout.write(f"  . Skipped: {employee.full_name} (No change)")
                            pass
                    else:
                        # AUTO-CREATE NEW EMPLOYEE
                        # Generate unique NIK based on Telegram ID
                        new_nik = f"TELE-{tele_id}"[:20] 
                        
                        location_obj = None
                        if location_code:
                            location_obj = WorkLocation.objects.filter(code=location_code).first()

                        Employee.objects.create(
                            nik=new_nik,
                            full_name=clean_name,
                            telegram_user_id=tele_id,
                            employee_type='HARIAN', # Default
                            home_base=location_obj,
                            is_active=True
                        )
                        self.stdout.write(f"  + Created: {clean_name} (ID: {tele_id})")
                        created_count += 1
                        
            self.stdout.write(self.style.SUCCESS(f"Sync complete. Updated: {updated_count}, Created: {created_count}, Not Found: {not_found_count} (Should be 0 now)"))


        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to sync data: {str(e)}"))
