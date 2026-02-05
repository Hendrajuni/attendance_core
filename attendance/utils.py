"""
Attendance Utilities

Shared helper functions for attendance processing across all data sources.
"""

from datetime import time
from django.utils import timezone


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
    
    return start <= current <= end


def determine_category(dt, schedule=None):
    """
    Determine log category based on datetime and optional schedule.
    
    This function standardizes time-slot categorization for attendance logs
    regardless of source (Telegram, Fingerprint, etc.).
    
    Args:
        dt: A datetime object (timezone-aware or naive).
            If naive, it will be treated as local time.
        schedule: Optional DailySchedule object for dynamic checkpoint detection.
                  If None, uses hardcoded fallback ranges.
    
    Returns:
        str: One of 'MASUK', 'CHECKPOINT_1', 'ISTIRAHAT', 'CHECKPOINT_2', 'PULANG', or 'UNKNOWN'
    
    Fallback Time Ranges (when no schedule):
        - 05:00 - 08:30 -> MASUK (Check-in)
        - 09:00 - 11:00 -> CHECKPOINT_1 (Mid-morning check)
        - 11:30 - 13:30 -> ISTIRAHAT (Lunch break)
        - 14:00 - 15:45 -> CHECKPOINT_2 (Afternoon check)
        - 16:00 - 23:59 -> PULANG (Check-out)
        - Otherwise -> UNKNOWN
    """
    # Handle None input
    if dt is None:
        return 'UNKNOWN'
    
    # Make aware if naive (assume local timezone)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    
    # Convert to local time for consistent categorization
    local_dt = timezone.localtime(dt)
    current_time = local_dt.time()
    
    # If schedule is provided, use schedule-based detection
    if schedule is not None:
        return _determine_category_with_schedule(current_time, schedule)
    
    # Fallback: Use hardcoded ranges (legacy behavior)
    return _determine_category_fallback(current_time)


def _determine_category_with_schedule(current_time, schedule):
    """
    Determine category using DailySchedule configuration.
    
    Priority order:
    1. CHECKPOINT_1 (if enabled and within range)
    2. CHECKPOINT_2 (if enabled and within range)
    3. ISTIRAHAT (break time)
    4. MASUK (scan-in window or before clock_in + tolerance)
    5. PULANG (scan-out window or after clock_out)
    6. UNKNOWN
    """
    # Check Checkpoint 1 (Telegram-specific)
    if schedule.enable_checkin_1:
        if is_within_range(current_time, schedule.checkin_1_start, schedule.checkin_1_end):
            return 'CHECKPOINT_1'
    
    # Check Checkpoint 2 (Telegram-specific)
    if schedule.enable_checkin_2:
        if is_within_range(current_time, schedule.checkin_2_start, schedule.checkin_2_end):
            return 'CHECKPOINT_2'
    
    # Check Break/Istirahat
    if is_within_range(current_time, schedule.break_start, schedule.break_end):
        return 'ISTIRAHAT'
    
    # Check MASUK (Clock-in window)
    # Use scan_in window if available, otherwise use clock_in time with tolerance
    if schedule.scan_in_start and schedule.scan_in_end:
        if is_within_range(current_time, schedule.scan_in_start, schedule.scan_in_end):
            return 'MASUK'
    else:
        # Fallback: 30 minutes before clock_in to clock_in + late_tolerance
        clock_in_mins = time_to_minutes(schedule.clock_in)
        if clock_in_mins:
            start_mins = max(0, clock_in_mins - 30)
            end_mins = clock_in_mins + schedule.late_tolerance + 30  # Allow 30 mins after tolerance
            current_mins = time_to_minutes(current_time)
            if start_mins <= current_mins <= end_mins:
                return 'MASUK'
    
    # Check PULANG (Clock-out window)
    if schedule.scan_out_start and schedule.scan_out_end:
        if is_within_range(current_time, schedule.scan_out_start, schedule.scan_out_end):
            return 'PULANG'
    else:
        # Fallback: After clock_out time
        clock_out_mins = time_to_minutes(schedule.clock_out)
        if clock_out_mins:
            current_mins = time_to_minutes(current_time)
            if current_mins >= clock_out_mins:
                return 'PULANG'
    
    return 'UNKNOWN'


def _determine_category_fallback(current_time):
    """
    Legacy fallback using hardcoded time ranges.
    Used when no DailySchedule is provided.
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


def get_employee_schedule_for_date(employee, target_date):
    """
    Get the applicable DailySchedule for an employee on a specific date.
    
    Args:
        employee: Employee model instance
        target_date: datetime.date object
    
    Returns:
        DailySchedule object or None if no assignment found
    """
    from django.db.models import Q
    from attendance.models import EmployeeShiftAssignment
    
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
        return assignment.shift_pattern.get_schedule_for_day(weekday)
    
    return None


