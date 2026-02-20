"""
Attendance Utilities

Shared helper functions for attendance processing across all data sources.
The Brain: Central logic for time-slot categorization based on employee shift assignments.
"""

from datetime import time, date, datetime
from django.utils import timezone
from django.db.models import Q


def time_to_minutes(t):
    """Convert a time object to minutes since midnight."""
    if t is None:
        return None
    return t.hour * 60 + t.minute


def is_within_range(current_time, start_time, end_time):
    """
    Check if current_time is within the range [start_time, end_time].
    All arguments should be datetime.time objects.
    """
    if start_time is None or end_time is None:
        return False
    
    current = time_to_minutes(current_time)
    start = time_to_minutes(start_time)
    end = time_to_minutes(end_time)
    
    if start <= end:
        # Standard range (e.g. 08:00 to 16:00)
        return start <= current <= end
    else:
        # Crossover range (e.g. 23:00 to 07:00)
        # In range if: >= 23:00 OR <= 07:00
        return current >= start or current <= end


def make_aware_timestamp(dt):
    """
    Ensure a datetime object is timezone-aware.
    
    Args:
        dt: A datetime object (can be naive or aware).
    
    Returns:
        datetime: Timezone-aware datetime object.
    """
    if dt is None:
        return None
    
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    
    return dt


def get_employee_schedule(employee, target_date):
    """
    Get the applicable DailySchedule for an employee on a specific date.
    
    Args:
        employee: Employee model instance
        target_date: datetime.date object
    
    Returns:
        tuple: (DailySchedule object or None, ShiftPattern object or None)
    """
    from attendance.models import EmployeeShiftAssignment, DailyShiftAssignment
    
    # 1. OPTIMIZATION: Check Daily Roster for Shift Workers
    # Only query this table if the employee is flagged as a shift worker
    if getattr(employee, 'is_shift_worker', False):
        roster = DailyShiftAssignment.objects.filter(
            employee=employee, 
            date=target_date
        ).select_related('shift').first()
        
        if roster:
            # Return direct schedule, no pattern
            return (roster.shift, None)

    # 2. Standard Weekly Pattern Logic (Fallback for Shift Workers, Default for Regulars)
    
    # Find active assignment for the target date
    assignment = EmployeeShiftAssignment.objects.filter(
        employee=employee,
        is_active=True,
        effective_from__lte=target_date
    ).filter(
        # effective_to is null OR effective_to >= target_date
        Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
    ).order_by('-effective_from').first()
    
    if assignment and assignment.shift_pattern:
        weekday = target_date.weekday()  # 0=Monday, 6=Sunday
        daily_schedule = assignment.shift_pattern.get_schedule_for_day(weekday)
        return (daily_schedule, assignment.shift_pattern)
    
    return (None, None)


def determine_category(employee, log_datetime):
    """
    Determine log category based on employee's shift assignment and log datetime.
    
    This is THE BRAIN function that standardizes time-slot categorization for 
    attendance logs regardless of source (Telegram, Fingerprint, etc.).
    
    Args:
        employee: Employee model instance
        log_datetime: A datetime object (timezone-aware or naive).
                      If naive, it will be treated as local time.
    
    Returns:
        tuple: (category: str, schedule_name: str or None)
            - category: One of 'MASUK', 'CHECKPOINT_1', 'ISTIRAHAT', 'CHECKPOINT_2', 'PULANG', 'LIBUR', 'UNKNOWN'
            - schedule_name: Name of the matched schedule for logging purposes
    
    Logic Flow:
        1. Identify weekday from log_datetime
        2. Query EmployeeShiftAssignment for active assignment on that date
        3. Get DailySchedule from ShiftPattern for that weekday
        4. Match log time against schedule windows
        5. Return category and schedule name
    """
    # Handle None input
    if log_datetime is None:
        return ('UNKNOWN', None)
    
    # Make aware if naive (assume local timezone)
    if timezone.is_naive(log_datetime):
        log_datetime = timezone.make_aware(log_datetime)
    
    # Convert to local time for consistent categorization
    local_dt = timezone.localtime(log_datetime)
    current_time = local_dt.time()
    target_date = local_dt.date()
    
    # Get employee's schedule for this date
    schedule, shift_pattern = get_employee_schedule(employee, target_date)
    
    # Explicit OFF Day Check (from Daily Roster)
    if schedule and schedule.code == 'OFF':
        return ('LIBUR', schedule.name)
    
    # No shift assigned or day is off (null in pattern)
    if schedule is None:
        if shift_pattern is not None:
            # Has pattern but this day is null = day off
            return ('LIBUR', shift_pattern.name)
        else:
            # No assignment at all - use fallback
            category = _determine_category_fallback(current_time)
            return (category, None)
    
    # Determine category based on schedule configuration
    category = _determine_category_with_schedule(current_time, schedule)
    return (category, schedule.name)


def _determine_category_with_schedule(current_time, schedule):
    """
    Determine category using DailySchedule configuration.
    
    Priority order:
    1. MASUK (scan-in window)
    2. CHECKPOINT_1 (if enabled and within range)
    3. ISTIRAHAT (break time)
    4. CHECKPOINT_2 (if enabled and within range)
    5. PULANG (scan-out window)
    6. UNKNOWN
    """
    # 1. Check MASUK (Clock-in window) - HIGHEST PRIORITY
    if schedule.scan_in_start and schedule.scan_in_end:
        if is_within_range(current_time, schedule.scan_in_start, schedule.scan_in_end):
            return 'MASUK'
    else:
        # Fallback: 60 minutes before clock_in to clock_in + late_tolerance + 30
        clock_in_mins = time_to_minutes(schedule.clock_in)
        if clock_in_mins:
            start_mins = max(0, clock_in_mins - 60)
            end_mins = clock_in_mins + (schedule.late_tolerance or 0) + 30
            current_mins = time_to_minutes(current_time)
            if start_mins <= current_mins <= end_mins:
                return 'MASUK'
    
    # 2. Check Checkpoint 1 (Telegram-specific)
    if schedule.enable_checkin_1:
        if is_within_range(current_time, schedule.checkin_1_start, schedule.checkin_1_end):
            return 'CHECKPOINT_1'
    
    # 3. Check Break/Istirahat
    if is_within_range(current_time, schedule.break_start, schedule.break_end):
        return 'ISTIRAHAT'
    
    # 4. Check Checkpoint 2 (Telegram-specific)
    if schedule.enable_checkin_2:
        if is_within_range(current_time, schedule.checkin_2_start, schedule.checkin_2_end):
            return 'CHECKPOINT_2'
    
    # 5. Check PULANG (Clock-out window)
    if schedule.scan_out_start and schedule.scan_out_end:
        if is_within_range(current_time, schedule.scan_out_start, schedule.scan_out_end):
            return 'PULANG'
    else:
        # Fallback: clock_out - 30 mins to midnight
        clock_out_mins = time_to_minutes(schedule.clock_out)
        if clock_out_mins:
            current_mins = time_to_minutes(current_time)
            if current_mins >= (clock_out_mins - 30):
                return 'PULANG'
    
    return 'UNKNOWN'


def _determine_category_fallback(current_time):
    """
    Legacy fallback using hardcoded time ranges.
    Used when employee has no shift assignment.
    """
    # Use integer comparison for HHMM format (e.g., 0830 = 8:30 AM)
    t = current_time.hour * 100 + current_time.minute

    if 500 <= t <= 830:
        return 'MASUK'
    elif 900 <= t <= 1100:
        return 'CHECKPOINT_1'
    elif 1130 <= t <= 1330:
        return 'ISTIRAHAT'
    elif 1400 <= t <= 1545:
        return 'CHECKPOINT_2'
    elif 1600 <= t <= 2359:
        return 'PULANG'
    
    return 'UNKNOWN'


# =============================================================================
# LEGACY COMPATIBILITY FUNCTION
# =============================================================================

def determine_category_simple(dt, schedule=None):
    """
    LEGACY: Simple determine_category for backward compatibility.
    Prefer using determine_category(employee, log_datetime) instead.
    
    Args:
        dt: datetime object
        schedule: Optional DailySchedule object
    
    Returns:
        str: Category name
    """
    if dt is None:
        return 'UNKNOWN'
    
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    
    local_dt = timezone.localtime(dt)
    current_time = local_dt.time()
    
    if schedule is not None:
        return _determine_category_with_schedule(current_time, schedule)
    
    return _determine_category_fallback(current_time)


    return _determine_category_fallback(current_time)


# =============================================================================
# USER SYNC UTILITIES
# =============================================================================

def fetch_users_from_machine(device):
    """
    Fetch users from ZK Device and create unverified Employee entries if new.
    Returns: (created_count, error_msg)
    """
    from zk import ZK
    from attendance.models import Employee
    
    conn = None
    try:
        zk = ZK(device.ip_address, port=device.port, timeout=10)
        conn = zk.connect()
        if not conn:
            return 0, [], "Gagal terhubung ke mesin"
            
        users = conn.get_users()
        created_count = 0
        samples = []
        
        for user in users:
            uid = user.uid
            name = user.name
            user_id = user.user_id # This is the numeric ID usually used
            
            # VALIDATION: Skip if user_id is not numeric (e.g. headers or garbage from machine)
            if not user_id or not str(user_id).isdigit():
                continue
            
            # Check if exists by device_user_id
            if not Employee.objects.filter(device_user_id=user_id).exists():
                # Create draft employee
                # Fix: nik max_length is 20. 
                # Use format: FG-{short_device_id}-{user_id}
                # Example: FG-a705bb-4510
                short_id = str(device.id)[-6:]
                nik_val = f"FG-{short_id}-{user_id}"
                
                # Ensure it fits
                if len(nik_val) > 20:
                    nik_val = nik_val[:20]
                
                Employee.objects.create(
                    full_name=name if name else f"User {user_id}",
                    nik=nik_val, 
                    device_user_id=user_id,
                    is_verified=False,
                    home_base=device.location  # Assume home base is where they are found
                )
                created_count += 1
                if len(samples) < 5:
                    samples.append(name if name else f"User {user_id}")
                
        return created_count, samples, None
        
    except Exception as e:
        return 0, [], str(e)
    finally:
        if conn:
            conn.disconnect()


def fetch_users_from_wa_source(source):
    """
    Fetch users from Spreadsheet (Sheet 'Data-Pegawai') and create unverified entries.
    Returns: (created_count, error_msg)
    """
    import pandas as pd
    from attendance.models import Employee
    
    try:
        # Construct URL for specific sheet (Configurable)
        sheet_name = source.employee_sheet_name if hasattr(source, 'employee_sheet_name') else "Data-Pegawai"
        csv_url = f"https://docs.google.com/spreadsheets/d/{source.spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        
        try:
            df = pd.read_csv(csv_url)
        except Exception:
             return 0, [], "Gagal membaca sheet 'Data-Pegawai'. Pastikan sheet ada."

        df.columns = [c.strip().upper() for c in df.columns]
        
        # Check columns
        if 'NAMA PEGAWAI' not in df.columns or 'NOMOR WA' not in df.columns:
             return 0, [], "Kolom 'NAMA PEGAWAI' atau 'NOMOR WA' tidak ditemukan."
             
        created_count = 0
        samples = []
        
        for _, row in df.iterrows():
            nama = str(row.get('NAMA PEGAWAI', '')).strip()
            no_wa = str(row.get('NOMOR WA', '')).strip()
            
            if not no_wa:
                continue
                
            # Clean Phone Number (simple)
            clean_wa = no_wa.replace('-', '').replace(' ', '')
            
            # Check if exists
            if not Employee.objects.filter(phone_number=clean_wa).exists():
                 Employee.objects.create(
                    full_name=nama if nama else f"WA User {clean_wa}",
                    nik=f"WA.{clean_wa[-6:]}", # Temp NIK
                    phone_number=clean_wa,
                    is_verified=False,
                    home_base=source.location
                )
                 created_count += 1
                 if len(samples) < 5:
                    samples.append(nama if nama else f"WA User {clean_wa}")
                 
        return created_count, samples, None

    except Exception as e:
        # Check for HTTPError (e.g. 401 Unauthorized)
        import urllib.error
        if isinstance(e, urllib.error.HTTPError):
            if e.code == 401 or e.code == 403:
                print(f"[SPREADSHEET ERROR] Permission Denied: {e}")
                return 0, [], "Gagal: Spreadsheet tidak publik. Ubah izin ke 'Anyone with the link'."
            elif e.code == 404:
                print(f"[SPREADSHEET ERROR] Not Found: {e}")
                return 0, [], "Gagal: Spreadsheet tidak ditemukan (404)."
        
        # Generic error
        print(f"[SPREADSHEET ERROR] {str(e)}")
        return 0, [], f"Error: {str(e)}"
