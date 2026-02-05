import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from attendance.models import Employee, WorkLocation


class Command(BaseCommand):
    help = 'Sync Mandor/Employee data and Telegram IDs from Google Sheet CSV'

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
            default='PR',  # Default to Pulau Raman
            help='Code of WorkLocation to assign for new employees (e.g. PR, HO)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving to database',
        )

    def handle(self, *args, **kwargs):
        url = kwargs['url']
        location_code = kwargs.get('location', 'PR')
        dry_run = kwargs.get('dry_run', False)
        
        self.stdout.write(f"Reading data from {url}...")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved"))

        try:
            df = pd.read_csv(url)
            # Normalize column names
            df.columns = [c.strip().upper() for c in df.columns]
            
            self.stdout.write(f"Columns found: {list(df.columns)}")
            
            # Check required columns - support both naming conventions
            name_col = None
            tele_col = None
            phone_col = None  # NEW: NOMOR WA column
            
            for col in df.columns:
                if 'NAMA' in col and 'PEGAWAI' in col:
                    name_col = col
                elif 'TELE' in col and ('USER' in col or 'ID' in col):
                    tele_col = col
                elif 'NOMOR' in col and 'WA' in col:
                    phone_col = col
            
            if not name_col or not tele_col:
                self.stdout.write(self.style.ERROR(f"CSV missing required columns. Found: {list(df.columns)}"))
                self.stdout.write(self.style.ERROR(f"  Need: NAMA PEGAWAI and TELE USERID"))
                return

            self.stdout.write(f"Using columns: name='{name_col}', tele='{tele_col}', phone='{phone_col}'")
            
            # Get location for new employees
            location_obj = WorkLocation.objects.filter(code=location_code).first()
            if location_obj:
                self.stdout.write(f"Location for new employees: {location_obj.name} ({location_code})")
            else:
                self.stdout.write(self.style.WARNING(f"Location '{location_code}' not found. New employees will have no home_base."))

            updated_count = 0
            created_count = 0
            skipped_count = 0

            with transaction.atomic():
                for index, row in df.iterrows():
                    raw_name = str(row[name_col]).strip()
                    tele_id_raw = row[tele_col]
                    
                    # Get phone number if column exists
                    phone_raw = row[phone_col] if phone_col and phone_col in df.columns else None
                    phone_number = None
                    if phone_raw and not pd.isna(phone_raw):
                        phone_number = str(int(float(phone_raw))) if isinstance(phone_raw, (int, float)) else str(phone_raw).strip()
                    
                    # Handle NaN and convert to string
                    if pd.isna(tele_id_raw):
                        self.stdout.write(self.style.WARNING(f"  ! Row {index+1}: '{raw_name}' - No Telegram ID, skipping"))
                        skipped_count += 1
                        continue
                    
                    tele_id = str(int(float(tele_id_raw))) if isinstance(tele_id_raw, (int, float)) else str(tele_id_raw).strip()

                    # Basic validation
                    if not raw_name or raw_name.lower() == 'nan':
                        continue
                    if not tele_id or tele_id.lower() == 'nan':
                        skipped_count += 1
                        continue

                    # Clean name - remove "|" annotations like "| PROGRAMMER"
                    clean_name = raw_name.split('|')[0].strip()
                    clean_name = " ".join(clean_name.split())  # Normalize spaces

                    # SEARCH: Try to find existing employee
                    employee = None
                    match_method = None
                    
                    # Strategy 1: Exact match by Telegram ID (already assigned)
                    employee = Employee.objects.filter(telegram_user_id=tele_id).first()
                    if employee:
                        match_method = "Telegram ID"
                    
                    # Strategy 2: Exact name match
                    if not employee:
                        employee = Employee.objects.filter(full_name__iexact=clean_name, is_active=True).first()
                        if employee:
                            match_method = "Exact Name"
                    
                    # Strategy 3: Contains match
                    if not employee:
                        matches = Employee.objects.filter(full_name__icontains=clean_name, is_active=True)
                        if matches.count() == 1:
                            employee = matches.first()
                            match_method = "Contains"
                        elif matches.count() > 1:
                            self.stdout.write(self.style.WARNING(
                                f"  ? Row {index+1}: '{clean_name}' matches {matches.count()} employees, skipping"
                            ))
                            skipped_count += 1
                            continue

                    if employee:
                        # UPDATE existing employee - telegram_user_id and phone_number
                        updated_fields = []
                        if employee.telegram_user_id != tele_id:
                            employee.telegram_user_id = tele_id
                            updated_fields.append('tele')
                        if phone_number and employee.phone_number != phone_number:
                            employee.phone_number = phone_number
                            updated_fields.append('phone')
                        
                        if updated_fields and not dry_run:
                            employee.save()
                            self.stdout.write(self.style.SUCCESS(
                                f"  ✓ Updated [{match_method}]: {employee.full_name} -> {', '.join(updated_fields)}"
                            ))
                            updated_count += 1
                    else:
                        # CREATE new employee as UNVERIFIED (goes to Pendaftaran Baru)
                        new_nik = f"TELE-{tele_id}"[:20]
                        now = timezone.now()
                        
                        if not dry_run:
                            Employee.objects.create(
                                nik=new_nik,
                                full_name=clean_name,
                                telegram_user_id=tele_id,
                                phone_number=phone_number,  # NEW: Store phone number
                                employee_type='HARIAN',
                                home_base=location_obj,
                                is_active=True,
                                is_verified=False,
                                imported_at=now,
                            )
                        self.stdout.write(self.style.SUCCESS(
                            f"  + Created (Draft): {clean_name} (Phone: {phone_number})"
                        ))
                        created_count += 1
                
                if dry_run:
                    # Rollback in dry run
                    transaction.set_rollback(True)
                        
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 50))
            self.stdout.write(self.style.SUCCESS(f"Sync Complete!"))
            self.stdout.write(f"  ✓ Created: {created_count}")
            self.stdout.write(f"  ○ Updated: {updated_count}")
            self.stdout.write(f"  ? Skipped: {skipped_count}")
            self.stdout.write(self.style.SUCCESS("=" * 50))

        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f"Failed to sync data: {str(e)}"))
            self.stdout.write(traceback.format_exc())

