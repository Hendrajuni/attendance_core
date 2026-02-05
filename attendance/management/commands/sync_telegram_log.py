import pandas as pd
from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import Employee, AttendanceLog
from attendance.utils import determine_category


class Command(BaseCommand):
    help = 'Sync Attendance Logs from Telegram Bot Spreadsheet (CSV)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            required=True,
            help='URL of the CSV file (Published Google Sheet)',
        )
        parser.add_argument(
            '--month',
            type=int,
            required=False,
            help='Filter by Month (1-12)',
        )
        parser.add_argument(
            '--year',
            type=int,
            required=False,
            help='Filter by Year (e.g. 2026)',
        )

    def handle(self, *args, **kwargs):
        url = kwargs['url']
        filter_month = kwargs.get('month')
        filter_year = kwargs.get('year')

        self.stdout.write(f"Reading logs from {url}...")
        if filter_month and filter_year:
             self.stdout.write(f"Filtering for Month: {filter_month}, Year: {filter_year}")

        try:
            df = pd.read_csv(url)
            
            created_count = 0
            skipped_count = 0
            filtered_count = 0
            
            for index, row in df.iterrows():
                try:
                    # Column Mapping based on Debug Result
                    # Headers: ['TANGGAL', 'JAM ABSEN', 'NAMA PEGAWAI', 'NOMOR WA', 'KOORDINAT', ...]
                    
                    tgl_str = str(row.get('TANGGAL', '')).strip()
                    jam_str = str(row.get('JAM ABSEN', '')).strip()
                    user_id = str(row.get('NOMOR WA', '')).strip() # Using WA Number as ID? Or is it Telegram ID? Assuming ID for now based on previous context.
                    nama = row.get('NAMA PEGAWAI')
                    coord = str(row.get('KOORDINAT', ''))
                    
                    if not tgl_str or not jam_str:
                        continue
                        
                    # Split Coordinate "lat, long"
                    lat, lng = None, None
                    if ',' in coord:
                        try:
                            lat_part, lng_part = coord.split(',')
                            lat = float(lat_part.strip())
                            lng = float(lng_part.strip())
                        except:
                            pass

                    # 1. Parse Timestamp (Combine Date + Time)
                    try:
                        # Date format likely DD/MM/YYYY based on "02/10/2023"
                        full_ts_str = f"{tgl_str} {jam_str}"
                        timestamp = pd.to_datetime(full_ts_str, dayfirst=True).to_pydatetime()
                        
                        if timezone.is_naive(timestamp):
                            timestamp = timezone.make_aware(timestamp)
                    except Exception as e:
                        # self.stdout.write(self.style.WARNING(f"  ! Invalid date: {full_ts_str}"))
                        continue

                    # OPTIMIZATION: Filter by Date
                    if filter_year and timestamp.year != filter_year:
                        filtered_count += 1
                        continue
                    if filter_month and timestamp.month != filter_month:
                        filtered_count += 1
                        continue

                    # 2. Find Employee by Telegram ID
                    # user_id column is "NOMOR WA", verify if this matches telegram_user_id in DB
                    employee = Employee.objects.filter(telegram_user_id=user_id, is_active=True).first()
                    
                    if not employee:
                        # Fallback: Try searching by Name if ID fails? (Dangerous but optional)
                        # For now, strict on ID
                        skipped_count += 1
                        continue

                    # 3. Determine Category Logic
                    category = determine_category(timestamp)

                    # 4. Create Attendance Log
                    log, created = AttendanceLog.objects.get_or_create(
                        employee=employee,
                        timestamp=timestamp,
                        defaults={
                            'status': 'HADIR',
                            'source_type': 'TELEGRAM',
                            'verification_method': 'GPS' if pd.notna(lat) else 'MANUAL',
                            'captured_at': employee.home_base,
                            'latitude': lat if pd.notna(lat) else None,
                            'longitude': lng if pd.notna(lng) else None,
                            'notes': nama, # Save raw name from log for reference
                            'log_category': category
                        }
                    )

                    if created:
                        created_count += 1
                
                except Exception as row_err:
                    self.stdout.write(self.style.ERROR(f"  ! Error row {index}: {row_err}"))
                    continue

            self.stdout.write(self.style.SUCCESS(f"Sync complete. New Logs: {created_count}, Skipped (Unknown User): {skipped_count}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to sync logs: {str(e)}"))
