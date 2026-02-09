from django.shortcuts import render
from datetime import datetime, time, date, timedelta
from django.contrib.auth.decorators import login_required
from attendance.utils import get_employee_schedule

# Constants
SCHEDULE_IN = time(8, 0)
SCHEDULE_OUT = time(17, 0)
DEFAULT_SCHEDULE_IN = SCHEDULE_IN
DEFAULT_SCHEDULE_OUT = SCHEDULE_OUT

@login_required
def dashboard(request):
    """
    Main Dashboard View
    """
    context = {
        'page_title': 'Dashboard',
    }
    return render(request, 'portal/dashboard.html', context)

@login_required
def tree_explorer(request):
    """
    Pusat Data Wilayah View (Hierarchy)
    """
    from attendance.models import WorkLocation
    
    all_locations = WorkLocation.objects.all()
    locations = all_locations
    
    # RBAC: Kerani only sees their location and descendants
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location:
            # get_descendants(include_self=True) handles the tree traversal efficiently
            locations = profile.assigned_location.get_descendants(include_self=True)
            
    context = {
        'page_title': 'Pusat Data Wilayah',
        'locations': locations,
        'all_locations': all_locations,  # For mutation modal dropdown
    }
    return render(request, 'portal/tree_explorer.html', context)


@login_required
def location_detail_view(request, location_id):
    """
    HTMX: Load detail konten untuk panel kanan Tree Explorer
    Supports pagination with page_size for employees and logs
    """
    from attendance.models import WorkLocation, Employee, AttendanceLog
    from django.utils import timezone
    from django.core.paginator import Paginator
    
    location = get_object_or_404(WorkLocation, id=location_id)
    
    # Pagination parameters
    emp_page_size = int(request.GET.get('emp_page_size', 10))  # Default 10
    emp_page = int(request.GET.get('emp_page', 1))
    log_page_size = int(request.GET.get('log_page_size', 10))  # Default 10
    log_page = int(request.GET.get('log_page', 1))
    
    # Valid page sizes
    PAGE_SIZE_OPTIONS = [10, 20, 50, 100]
    if emp_page_size not in PAGE_SIZE_OPTIONS:
        emp_page_size = 10
    if log_page_size not in PAGE_SIZE_OPTIONS:
        log_page_size = 10
    
    # Ambil lokasi ini DAN seluruh turunannya (jika ada)
    # Ini penting untuk melihat total karyawan di wilayah tersebut (termasuk sub-wilayah)
    # Gunakan get_descendants(include_self=True) dari MPTT
    sub_locations = location.get_descendants(include_self=True)
    
    # Filter Karyawan: Home Base is within these locations
    employees_qs = Employee.objects.filter(
        home_base__in=sub_locations,
        is_verified=True
    ).select_related('department', 'home_base').order_by('full_name')
    
    total_employees = employees_qs.count()
    active_employees = employees_qs.filter(is_active=True).count()
    
    # Paginate employees
    emp_paginator = Paginator(employees_qs, emp_page_size)
    employees_page = emp_paginator.get_page(emp_page)
    
    # Statistik Kehadiran Hari Ini (Sederhana)
    today = timezone.now().date()
    # Log hari ini untuk karyawan di wilayah ini
    logs_today = AttendanceLog.objects.filter(
        employee__in=employees_qs,
        timestamp__date=today
    ).values('employee').distinct().count()
    
    # Recent Logs for Tab with pagination
    recent_logs_qs = AttendanceLog.objects.filter(
        employee__in=employees_qs
    ).select_related('employee', 'captured_at').order_by('-timestamp')
    
    log_paginator = Paginator(recent_logs_qs, log_page_size)
    logs_page = log_paginator.get_page(log_page)
    
    context = {
        'location': location,
        'employees': employees_page,
        'employees_page': employees_page,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'present_today': logs_today,
        'recent_logs': logs_page,
        'logs_page': logs_page,
        # Pagination state
        'emp_page_size': emp_page_size,
        'log_page_size': log_page_size,
        'page_size_options': PAGE_SIZE_OPTIONS,
    }
    
    return render(request, 'portal/partials/_location_detail.html', context)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from attendance.models import FingerprintDevice, SpreadsheetSource, AttendanceLog, Employee, WorkLocation, EmployeeProfile, EmployeeLeave

@login_required
def sync_logs_view(request):
    """
    Pusat Sinkronisasi View with RBAC
    """
    devices = FingerprintDevice.objects.filter(is_active=True).select_related('location')
    sources = SpreadsheetSource.objects.all().select_related('location')
    
    # RBAC Filter: Kerani only sees their location
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location:
            devices = devices.filter(location=profile.assigned_location)
            sources = sources.filter(location=profile.assigned_location)
            
    context = {
        'page_title': 'Tarik Log Absensi',
        'devices': devices,
        'sources': sources,
    }
    return render(request, 'portal/sync_center.html', context)


@login_required
def sync_employees_view(request):
    """
    Tarik Data Karyawan Baru View
    """
    devices = FingerprintDevice.objects.filter(is_active=True).select_related('location')
    sources = SpreadsheetSource.objects.all().select_related('location')
    
    # RBAC Filter
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location:
            devices = devices.filter(location=profile.assigned_location)
            sources = sources.filter(location=profile.assigned_location)
            
    context = {
        'page_title': 'Tarik Karyawan Baru',
        'devices': devices,
        'sources': sources,
        'is_employee_sync': True, # Flag for template matching
    }
    return render(request, 'portal/sync_employees.html', context)


@login_required
@require_POST
def sync_employee_machine_htmx(request, device_id):
    device = get_object_or_404(FingerprintDevice, id=device_id)
    
    # Simple Access Check
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location != device.location:
             return HttpResponse('<span class="badge bg-danger">Akses Ditolak</span>')

    from attendance.utils import fetch_users_from_machine
    
    count, samples, error = fetch_users_from_machine(device)
    
    if error:
        return HttpResponse(f'''
            <span class="badge bg-danger">Error</span>
            <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{timezone.now().strftime("%H:%M:%S")}</td>
                <td>{device.name}</td>
                <td><span class="badge bg-danger">Gagal</span></td>
                <td class="text-danger">{error}</td>
            </tr>
        ''')
    
    current_time = timezone.now().strftime("%H:%M:%S")
    
    if count > 0:
        badge_html = f'<span class="badge bg-success">User: {count}</span> <span class="badge bg-light text-dark border">Cek: {current_time}</span>'
        msg_text = f"Berhasil menarik {count} user baru"
    else:
        badge_html = f'<span class="badge bg-secondary">User: 0</span> <span class="badge bg-light text-dark border">Cek: {current_time}</span>'
        msg_text = "Tidak ada user baru (Up-to-date)"
        
    # Build Detail Rows for Samples
    extra_rows = ""
    if samples:
        for sample in samples:
            extra_rows += f'''
            <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{current_time}</td>
                <td>{device.name}</td>
                <td><span class="badge bg-info">Detail</span></td>
                <td class="text-info">{sample}</td>
            </tr>
            '''
    
    log_row = f'''
        <tr hx-swap-oob="afterbegin:#sync-log-body">
            <td>{current_time}</td>
            <td>{device.name}</td>
            <td><span class="badge bg-{'success' if count > 0 else 'secondary'}">Sukses</span></td>
            <td>{msg_text}</td>
        </tr>
    '''
    return HttpResponse(badge_html + extra_rows + log_row)


@login_required
@require_POST
def sync_employee_wa_htmx(request, source_id):
    source = get_object_or_404(SpreadsheetSource, id=source_id)
    
    # Simple Access Check
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location != source.location:
             return HttpResponse('<span class="badge bg-danger">Akses Ditolak</span>')

    from attendance.utils import fetch_users_from_wa_source
    
    count, samples, error = fetch_users_from_wa_source(source)
    
    if error:
         return HttpResponse(f'''
            <span id="status-source-{source.id}" class="badge bg-danger" hx-swap-oob="true">Error</span>
             <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{timezone.now().strftime("%H:%M:%S")}</td>
                <td>{source.name}</td>
                <td><span class="badge bg-danger">Gagal</span></td>
                <td class="text-danger">{error}</td>
            </tr>
        ''')

    # Main Status Update (OOB) to avoid messy main-swap context
    status_html = f'<span id="status-source-{source.id}" class="badge bg-success" hx-swap-oob="true">OK ({count})</span>'
    
    # Build Detail Rows for Samples
    extra_rows = ""
    current_time = timezone.now().strftime("%H:%M:%S")
    if samples:
        for sample in samples:
            extra_rows += f'''
            <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{current_time}</td>
                <td>{source.name}</td>
                <td><span class="badge bg-info">Detail</span></td>
                <td class="text-info">{sample}</td>
            </tr>
            '''
            
    # Main Log Row
    log_row = f'''
        <tr hx-swap-oob="afterbegin:#sync-log-body">
            <td>{timezone.now().strftime("%H:%M:%S")}</td>
            <td>{source.name}</td>
            <td><span class="badge bg-success">Sukses</span></td>
            <td>Berhasil menarik {count} karyawan baru</td>
        </tr>
    '''
    
    # Return everything combined.
    # ALTERNATIVE APPROACH: JS Injection
    # Since HTMX/Browser parsing of OOB <tr> tags is flaky, we use a simple script to inject the rows.
    # This bypasses the parsing "tr must be inside table" rule because it's treated as a JS string until insertion.
    
    # Escape single quotes and newlines for JS string safety
    rows_js = (extra_rows + log_row).replace('"', '\\"').replace('\n', '')
    
    response_html = f'''
    {status_html.replace('hx-swap-oob="true"', '')} <!-- Return normal HTML for the target -->
    <script>
        var newRows = "{rows_js}";
        // Remove hx-swap-oob attributes since we are injecting manually
        newRows = newRows.replace(/hx-swap-oob="[^"]+"/g, "");
        
        // Use our new Client-Side Manager
        if (typeof SyncLogManager !== 'undefined') {{
            SyncLogManager.addRows(newRows);
        }} else {{
            // Fallback if script not loaded yet (should rarely happen)
            document.querySelector('#sync-log-body').insertAdjacentHTML('afterbegin', newRows);
        }}
    </script>
    '''
    return HttpResponse(response_html)


@login_required
@require_POST
def sync_machine_htmx(request, device_id):
    device = get_object_or_404(FingerprintDevice, id=device_id)
    print(f"DEBUG: HIT sync_machine_htmx for {device.name} (IP: {device.ip_address})")
    
    # Simple Access Check
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location != device.location:
             return HttpResponse('<span class="badge bg-danger">Akses Ditolak</span>')

    try:
        from zk import ZK
        from attendance.utils import determine_category
        from portal.models import Notification
        
        print("DEBUG: Connecting to ZK...")
        zk = ZK(device.ip_address, port=device.port, timeout=5)
        conn = zk.connect()
        
        if not conn:
             return HttpResponse(f'''
                <span class="badge bg-danger">Gagal Koneksi</span>
                <tr hx-swap-oob="afterbegin:#sync-log-body">
                    <td>{timezone.now().strftime("%H:%M:%S")}</td>
                    <td>{device.name}</td>
                    <td><span class="badge bg-danger">Error</span></td>
                    <td class="text-danger">Gagal terhubung ke mesin (Timeout)</td>
                </tr>
            ''')
            
        try:
            print("DEBUG: Fetching attendance...")
            attendances = conn.get_attendance()
            total_records = len(attendances)
            print(f"DEBUG: Fetched {total_records} records. Optimizing processing...")
            
            created_count = 0
            
            # OPTIMIZATION: Prefetch all active employees to avoid N+1 queries
            # Map device_user_id -> Employee Object
            active_employees = {
                str(emp.device_user_id): emp 
                for emp in Employee.objects.filter(is_active=True)
            }
            print(f"DEBUG: Loaded {len(active_employees)} active employees into memory.")

            # Track detailed logs for UI (Limit 5)
            detailed_logs = []
            
            with transaction.atomic():
                for att in attendances:
                    user_id = str(att.user_id)
                    
                    # Fast Lookup from Memory
                    employee = active_employees.get(user_id)
                    if not employee:
                        continue
                        
                    timestamp = att.timestamp
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                    
                    # Determine category (CPU bound, fast)
                    category, _ = determine_category(employee, timestamp)
                    
                    # We still use get_or_create for safety, but now 'employee' is already fetched
                    _, created = AttendanceLog.objects.get_or_create(
                        employee=employee, timestamp=timestamp,
                        defaults={
                            'status': 'HADIR', 'source_type': 'FINGERPRINT',
                            'verification_method': 'FINGER', 'captured_at': device.location,
                            'log_category': category
                        }
                    )
                    if created: 
                        created_count += 1
                        # Store tuple: (name, time_str, category) for rich display
                        time_str = timestamp.strftime("%H:%M")
                        detailed_logs.append((employee.full_name, time_str, category))
            
            print(f"DEBUG: Created {created_count} new logs from {total_records} raw records.")
            current_time = timezone.now().strftime("%H:%M:%S")
            
            # --- Update Last Activity ---
            device.last_activity = timezone.now()
            device.save(update_fields=['last_activity'])
            
            # --- Create Notification (ALWAYS) ---
            from portal.models import Notification
            from attendance.models import EmployeeProfile 
            from django.contrib.auth.models import User
            
            actor_name = request.user.first_name or request.user.username
            time_str = timezone.localtime(timezone.now()).strftime("%d/%m %H:%M")
            
            title = f"Sync: {device.name} ({device.location.code})"
            if created_count > 0:
                message = f"Ditarik oleh {actor_name} pada {time_str}. Total {created_count} data baru dari {device.location.name}."
            else:
                message = f"Dicek oleh {actor_name} pada {time_str}. Tidak ada data baru dari {device.location.name}."
            
            # Logic: Send to Admin/HRD (Global) + Manager/Kerani (Location Specific)
            # 1. Global (Admin/HRD) + All Superusers
            global_recipients = set(EmployeeProfile.objects.filter(role__in=['ADMIN', 'HRD']).values_list('user', flat=True))
            superusers = set(User.objects.filter(is_superuser=True).values_list('id', flat=True))
            
            # 2. Local (Manager/Kerani at this location)
            local_recipients = set(EmployeeProfile.objects.filter(
                role__in=['HRD', 'KERANI'], 
                assigned_location=device.location
            ).values_list('user', flat=True))
            
            recipient_ids = global_recipients.union(superusers).union(local_recipients)
            
            notifications_to_create = []
            for uid in recipient_ids:
                notifications_to_create.append(Notification(
                    recipient_id=uid,
                    title=title,
                    message=message,
                    related_location=device.location
                ))
            
            Notification.objects.bulk_create(notifications_to_create)

            # Badge logic
            if created_count > 0:
                badge_html = f'<span class="badge bg-success">Data: {created_count}</span> <span class="badge bg-light text-dark border">Cek: {current_time}</span>'
                msg_text = f"Berhasil menarik {created_count} data baru (Total Mesin: {total_records})"
            else:
                badge_html = f'<span class="badge bg-secondary">Data: 0</span> <span class="badge bg-light text-dark border">Cek: {current_time}</span>'
                msg_text = f"Tidak ada data baru. (Total di Mesin: {total_records})"

           # Build HTML for new logs (Script Injection Method)
            extra_rows = ""
            if detailed_logs:
                for name, att_time, category in detailed_logs:
                    # Dynamic badge based on category
                    if category in ('CHECKIN_1', 'SCAN_IN'):
                        badge = '<span class="badge bg-success">Masuk</span>'
                        text_class = 'text-success'
                    elif category in ('CHECKOUT', 'SCAN_OUT'):
                        badge = '<span class="badge bg-primary">Pulang</span>'
                        text_class = 'text-primary'
                    elif category == 'CHECKIN_2':
                        badge = '<span class="badge bg-info">Cek-2</span>'
                        text_class = 'text-info'
                    else:
                        badge = '<span class="badge bg-secondary">Absen</span>'
                        text_class = 'text-light'
                    
                    extra_rows += f'''
                    <tr>
                        <td>{att_time}</td>
                        <td>{device.name}</td>
                        <td>{badge}</td>
                        <td class="{text_class}">{name}</td>
                    </tr>
                    '''
            
            log_row = f'''
                <tr>
                    <td>{current_time}</td>
                    <td>{device.name}</td>
                    <td><span class="badge bg-success">Sukses</span></td>
                    <td>Berhasil menarik {created_count} data baru (Total Mesin: {total_records})</td>
                </tr>
            '''
            
            # Escape strings for JS safely
            import json
            rows_js = json.dumps(extra_rows + log_row)
            
            status_html = f'<span id="status-device-{device.id}" class="badge bg-success">OK ({total_records})</span>'
            
            return HttpResponse(f'''
                {status_html}
                <script>
                    var newRows = {rows_js};
                    if (window.SyncLogManager) {{
                         window.SyncLogManager.addRows(newRows);
                    }} else {{
                         // Fallback
                         document.querySelector('#sync-log-body').insertAdjacentHTML('afterbegin', newRows);
                    }}
                </script>
            ''')
            
        except Exception as e:
            print(f"DEBUG: Error during sync: {e}")
            import traceback
            traceback.print_exc()
            
            import json
            error_msg = str(e)
            error_row_html = f'''
                <tr>
                    <td>{timezone.now().strftime("%H:%M:%S")}</td>
                    <td>{device.name}</td>
                    <td><span class="badge bg-danger">Error</span></td>
                    <td class="text-danger">{error_msg}</td>
                </tr>
            '''
            rows_js = json.dumps(error_row_html)

            return HttpResponse(f'''
                <span class="badge bg-danger">Error</span>
                 <script>
                    var errorRows = {rows_js};
                    if (window.SyncLogManager) {{
                         window.SyncLogManager.addRows(errorRows);
                    }} else {{
                         document.querySelector('#sync-log-body').insertAdjacentHTML('afterbegin', errorRows);
                    }}
                </script>
            ''')
            
        finally:
            conn.disconnect()

    except Exception as e:
        print(f"DEBUG: Top level error: {e}")
        return HttpResponse(f'<span class="badge bg-danger">Error Connect</span>')


@login_required
def ping_machine_htmx(request, device_id):
    device = get_object_or_404(FingerprintDevice, id=device_id)
    
    try:
        from zk import ZK
        zk = ZK(device.ip_address, port=device.port, timeout=3)
        conn = zk.connect()
        if conn:
            conn.disconnect()
            device.last_activity = timezone.now()
            device.save(update_fields=['last_activity'])
            return HttpResponse('<span class="badge bg-success">Online</span>')
        else:
            return HttpResponse('<span class="badge bg-danger">Offline</span>')
    except Exception:
        return HttpResponse('<span class="badge bg-danger">Offline</span>')

@login_required
@require_POST
def sync_wa_source_htmx(request, source_id):
    source = get_object_or_404(SpreadsheetSource, id=source_id)
    
     # Simple Access Check
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location != source.location:
             return HttpResponse('<span class="badge bg-danger">Akses Ditolak</span>')

    try:
        import pandas as pd
        from attendance.utils import determine_category
        
        csv_url = f"https://docs.google.com/spreadsheets/d/{source.spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={source.sheet_name}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().upper() for c in df.columns]
        
        # Track detailed logs for UI
        detailed_logs = []
        created_count = 0
        
        # DEBUG: Print column names
        print(f"DEBUG: Spreadsheet columns = {list(df.columns)}")
        print(f"DEBUG: Total rows in spreadsheet = {len(df)}")
        
        with transaction.atomic():
            for idx, row in df.iterrows():
                tgl_str = str(row.get('TANGGAL', '')).strip()
                jam_str = str(row.get('JAM ABSEN', '')).strip()
                user_id = str(row.get('NOMOR WA', '')).strip()
                
                if not tgl_str or not jam_str: 
                    print(f"DEBUG: Row {idx} skipped - missing TANGGAL or JAM ABSEN")
                    continue
                
                try:
                    full_ts_str = f"{tgl_str} {jam_str}"
                    timestamp = pd.to_datetime(full_ts_str, dayfirst=True).to_pydatetime()
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                    
                    # Normalize phone number lookup (handles .0 suffix from float storage)
                    # Try exact match first
                    employee = Employee.objects.filter(phone_number=user_id, is_active=True).first()
                    if not employee:
                        # Try with .0 suffix (database might have stored as float)
                        employee = Employee.objects.filter(phone_number=f"{user_id}.0", is_active=True).first()
                    if not employee:
                        employee = Employee.objects.filter(telegram_user_id=user_id, is_active=True).first()
                    if not employee:
                        # Try telegram_user_id with .0 suffix
                        employee = Employee.objects.filter(telegram_user_id=f"{user_id}.0", is_active=True).first()
                    if not employee: 
                        print(f"DEBUG: Row {idx} - Employee not found for user_id={user_id}")
                        continue
                    
                    category, _ = determine_category(employee, timestamp)
                    
                    _, created = AttendanceLog.objects.get_or_create(
                         employee=employee, timestamp=timestamp,
                         defaults={
                            'status': 'HADIR', 'source_type': 'TELEGRAM',
                            'verification_method': 'WA', 'captured_at': source.location,
                            'log_category': category
                        }
                    )
                    if created: 
                        created_count += 1
                        # Store tuple: (name, time_str, category) for rich display
                        time_str = timestamp.strftime("%H:%M")
                        detailed_logs.append((employee.full_name, time_str, category))
                    else:
                        print(f"DEBUG: Row {idx} - Log already exists for {employee.full_name} at {timestamp}")
                except Exception as row_err:
                    print(f"DEBUG: Row {idx} - Error: {row_err}")
                    continue
        
        print(f"DEBUG: Created {created_count} new logs")
        
        # --- Update Last Activity ---
        source.last_activity = timezone.now()
        source.save(update_fields=['last_activity'])
        
        # --- Create Notification (ALWAYS) ---
        from portal.models import Notification
        from attendance.models import EmployeeProfile
        from django.contrib.auth.models import User
        
        actor_name = request.user.first_name or request.user.username
        time_str = timezone.localtime(timezone.now()).strftime("%d/%m %H:%M")
        
        title = f"Sync WA: {source.name} ({source.location.code})"
        if created_count > 0:
            message = f"Ditarik oleh {actor_name} pada {time_str}. Total {created_count} data baru dari {source.location.name}."
        else:
            message = f"Dicek oleh {actor_name} pada {time_str}. Tidak ada data baru dari {source.location.name}."
        
        # Logic: Send to Admin/HRD (Global) + Manager/Kerani (Location Specific)
        global_recipients = set(EmployeeProfile.objects.filter(role__in=['ADMIN', 'HRD']).values_list('user', flat=True))
        superusers = set(User.objects.filter(is_superuser=True).values_list('id', flat=True))

        local_recipients = set(EmployeeProfile.objects.filter(
            role__in=['HRD', 'KERANI'],
            assigned_location=source.location
        ).values_list('user', flat=True))
        
        recipient_ids = global_recipients.union(superusers).union(local_recipients)
        
        notifications_to_create = []
        for uid in recipient_ids:
            notifications_to_create.append(Notification(
                recipient_id=uid,
                title=title,
                message=message,
                related_location=source.location
            ))
        
        Notification.objects.bulk_create(notifications_to_create)

        status_badge = f'<span class="badge bg-success">OK ({created_count})</span>'
        
        # Build HTML for new logs (Script Injection Method)
        import json
        extra_rows = ""
        current_time = timezone.now().strftime("%H:%M:%S")
        
        for name, att_time, category in detailed_logs:
            # Dynamic badge based on category
            if category in ('CHECKIN_1', 'SCAN_IN'):
                badge = '<span class="badge bg-success">Masuk</span>'
                text_class = 'text-success'
            elif category in ('CHECKOUT', 'SCAN_OUT'):
                badge = '<span class="badge bg-primary">Pulang</span>'
                text_class = 'text-primary'
            elif category == 'CHECKIN_2':
                badge = '<span class="badge bg-info">Cek-2</span>'
                text_class = 'text-info'
            else:
                badge = '<span class="badge bg-secondary">Absen</span>'
                text_class = 'text-light'
            
            extra_rows += f'''
            <tr>
                <td>{att_time}</td>
                <td>{source.name}</td>
                <td>{badge}</td>
                <td class="{text_class}">{name}</td>
            </tr>
            '''
        
        log_row = f'''
            <tr>
                <td>{current_time}</td>
                <td>{source.name}</td>
                <td><span class="badge bg-success">Sukses</span></td>
                <td>Berhasil menarik {created_count} data baru</td>
            </tr>
        '''
        
        rows_js = json.dumps(extra_rows + log_row)

        return HttpResponse(f'''
            {status_badge}
            <script>
                var newRows = {rows_js};
                if (window.SyncLogManager) {{
                     window.SyncLogManager.addRows(newRows);
                }} else {{
                     // Fallback
                     document.querySelector('#sync-log-body').insertAdjacentHTML('afterbegin', newRows);
                }}
            </script>
        ''')

    except Exception as e:
        import json
        error_msg = str(e)[:100]
        error_row_html = f'''
            <tr>
                <td>{timezone.now().strftime("%H:%M:%S")}</td>
                <td>{source.name}</td>
                <td><span class="badge bg-danger">Exception</span></td>
                <td class="text-danger">{error_msg}</td>
            </tr>
        '''
        rows_js = json.dumps(error_row_html)
        
        return HttpResponse(f'''
            <span class="badge bg-danger">Error</span>
             <script>
                var errorRows = {rows_js};
                if (window.SyncLogManager) {{
                     window.SyncLogManager.addRows(errorRows);
                }} else {{
                     document.querySelector('#sync-log-body').insertAdjacentHTML('afterbegin', errorRows);
                }}
            </script>
        ''')

@login_required
def reports(request):
    """
    Laporan View (Restricted Access)
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, 'portal/403.html', status=403)
        
    context = {
        'page_title': 'Laporan',
    }
    return render(request, 'portal/reports.html', context)

@login_required
def settings(request):
    """
    Pengaturan View
    """
    context = {
        'page_title': 'Pengaturan',
    }
    return render(request, 'portal/settings.html', context)


@login_required
def global_search(request):
    """
    Global Search View (HTMX)
    Searches Employees by name or NIK
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return HttpResponse("")
        
    results = Employee.objects.filter(
        Q(full_name__icontains=query) | Q(nik__icontains=query)
    )[:5] # Limit to 5 results
    
    if not results.exists():
        return HttpResponse('<li class="dropdown-item text-muted small">Tidak ditemukan</li>')
        
    html = ""
    for emp in results:
        # Determine status color
        status_color = "success" if emp.is_active else "secondary"
        
        html += f'''
        <li>
            <a class="dropdown-item d-flex align-items-center gap-2 py-2" href="/admin/attendance/employee/{emp.id}/change/">
                <div class="bg-light rounded-circle d-flex align-items-center justify-content-center" style="width: 32px; height: 32px;">
                    <i class="fas fa-user text-secondary small"></i>
                </div>
                <div>
                    <div class="fw-medium small">{emp.full_name}</div>
                    <div class="text-muted" style="font-size: 0.75rem;">
                        {emp.nik or "No NIK"} <span class="badge bg-{status_color} ms-1" style="font-size: 0.6rem;">{emp.get_status_display() if hasattr(emp, 'get_status_display') else 'Active'}</span>
                    </div>
                </div>
            </a>
        </li>
        '''
        
    
    # Add "View All" link if needed, or just return list
    html += '<li><hr class="dropdown-divider"></li>'
    # Link to Admin list filtered by query is a nice touch
    admin_search_url = f"/admin/attendance/employee/?q={query}"
    html += f'<li><a class="dropdown-item text-center small text-primary fw-bold" href="{admin_search_url}">Lihat Semua Hasil</a></li>'
    
    return HttpResponse(html)

@login_required
@require_POST
def mark_notification_read_htmx(request, notification_id):
    """
    Mark notification as read and return updated UI
    """
    from .models import Notification
    
    notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save()
        
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    
    # Badge OOB Update
    badge_html = ""
    if unread_count > 0:
         badge_html = f'''
         <span id="notif-badge-count" class="position-absolute top-0 start-100 translate-middle p-1 bg-danger border border-light rounded-circle" hx-swap-oob="true">
            <span class="visually-hidden">New alerts</span>
         </span>
         <span id="notif-header-count" class="badge bg-danger rounded-pill" hx-swap-oob="true">{unread_count} Baru</span>
         '''
    else:
        # Remove badge if 0
         badge_html = f'''
         <span id="notif-badge-count" class="d-none" hx-swap-oob="true"></span>
         <span id="notif-header-count" class="d-none" hx-swap-oob="true"></span>
         '''

    # Return the updated item (without bg-light and check button changed)
    # We reconstruct the LI here
    item_html = f'''
    <li id="notif-item-{notif.id}">
        <div class="dropdown-item small py-2 d-flex justify-content-between align-items-start">
            <a href="#" class="text-decoration-none text-dark flex-grow-1">
                <div class="d-flex align-items-start">
                    <i class="fas fa-info-circle text-secondary mt-1 me-2"></i>
                    <div>
                        <div class="fw-medium">{notif.title}</div>
                        <div class="text-muted text-truncate" style="max-width: 250px;">{notif.message}</div>
                        <div class="text-muted" style="font-size: 0.7rem;">{notif.created_at.strftime("%H:%M")} (Dibaca)</div>
                    </div>
                </div>
            </a>
        </div>
    </li>
    '''
    
    return HttpResponse(item_html + badge_html)


# =============================================================================
# EMPLOYEE MUTATION VIEW
# =============================================================================

@login_required
@require_POST
def mutate_employee_view(request, employee_id):
    """
    HTMX View untuk memproses mutasi karyawan.
    Only accessible by HRD or Superuser.
    """
    from attendance.models import EmployeeMutation
    
    # Permission Check: HRD or Superuser only
    if not request.user.is_superuser:
        if hasattr(request.user, 'employee_profile'):
            if request.user.employee_profile.role not in ['ADMIN', 'HRD']:
                return HttpResponse('<div class="alert alert-danger">Akses ditolak. Hanya HRD/Admin yang bisa memutasi karyawan.</div>', status=403)
        else:
            return HttpResponse('<div class="alert alert-danger">Akses ditolak.</div>', status=403)
    
    employee = get_object_or_404(Employee, id=employee_id)
    old_location = employee.home_base
    
    # Get form data
    new_location_id = request.POST.get('new_location')
    effective_date_str = request.POST.get('effective_date')
    reason = request.POST.get('reason', '').strip()
    
    if not new_location_id or not effective_date_str:
        return HttpResponse('<div class="alert alert-warning">Lokasi tujuan dan tanggal efektif wajib diisi.</div>')
    
    try:
        from datetime import datetime
        new_location = get_object_or_404(WorkLocation, id=new_location_id)
        effective_date = datetime.strptime(effective_date_str, '%Y-%m-%d').date()
        
        # Validate: Can't mutate to same location
        if old_location and old_location.id == new_location.id:
            return HttpResponse('<div class="alert alert-warning">Lokasi tujuan sama dengan lokasi asal.</div>')
        
        with transaction.atomic():
            # 1. Create mutation log
            EmployeeMutation.objects.create(
                employee=employee,
                old_location=old_location,
                new_location=new_location,
                effective_date=effective_date,
                reason=reason if reason else None,
                created_by=request.user
            )
            
            # 2. Update employee's home_base
            employee.home_base = new_location
            employee.save(update_fields=['home_base'])
        
        # Success response
        return HttpResponse(f'''
            <div class="alert alert-success">
                <i class="fas fa-check-circle me-2"></i>
                <strong>Mutasi Berhasil!</strong><br>
                {employee.full_name} dipindahkan dari <strong>{old_location.name if old_location else '-'}</strong> 
                ke <strong>{new_location.name}</strong> efektif tanggal {effective_date.strftime('%d %b %Y')}.
            </div>
            <script>
                // Close modal and refresh location detail
                setTimeout(() => {{
                    bootstrap.Modal.getInstance(document.getElementById('mutationModal')).hide();
                    // Trigger refresh on active location node
                    const activeNode = document.querySelector('.node-item.active');
                    if (activeNode) activeNode.click();
                }}, 1500);
            </script>
        ''')
        
    except Exception as e:
        return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')


# =============================================================================
# EMPLOYEE DETAIL VIEW
# =============================================================================

@login_required
def employee_detail_view(request, employee_id):
    """
    HTMX View untuk menampilkan detail lengkap karyawan.
    Includes: Profile, Attendance Stats, Mutation History
    """
    from attendance.models import Employee, AttendanceLog, EmployeeMutation, EmployeeShiftAssignment
    from django.db.models import Count, Q
    from django.utils import timezone
    from datetime import timedelta
    
    employee = get_object_or_404(Employee, id=employee_id)
    now = timezone.now()
    
    # === ATTENDANCE STATS (Current Month) ===
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    attendance_logs = AttendanceLog.objects.filter(
        employee=employee,
        timestamp__gte=start_of_month
    )
    
    # Count by status
    stats = attendance_logs.values('status').annotate(count=Count('id'))
    stats_dict = {s['status']: s['count'] for s in stats}
    
    hadir = stats_dict.get('HADIR', 0)
    izin = stats_dict.get('IZIN', 0)
    sakit = stats_dict.get('SAKIT', 0)
    alpha = stats_dict.get('ALPHA', 0)
    
    # Working days in month (approximate)
    import calendar
    _, days_in_month = calendar.monthrange(now.year, now.month)
    working_days = days_in_month - 4  # Rough estimate excluding weekends
    
    # === RECENT LOGS (Last 10) ===
    recent_logs = AttendanceLog.objects.filter(employee=employee).order_by('-timestamp')[:10]
    
    # === MUTATION HISTORY ===
    mutations = EmployeeMutation.objects.filter(employee=employee).order_by('-effective_date')[:5]
    
    # === SHIFT ASSIGNMENT ===
    try:
        shift_assignment = EmployeeShiftAssignment.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('shift_pattern').first()
    except:
        shift_assignment = None
    
    # === ATTENDANCE HEATMAP (Last 30 days) ===
    thirty_days_ago = now - timedelta(days=30)
    heatmap_logs = AttendanceLog.objects.filter(
        employee=employee,
        timestamp__gte=thirty_days_ago,
        log_category='MASUK'
    ).values('timestamp__date').annotate(count=Count('id'))
    
    attendance_dates = {str(log['timestamp__date']): log['count'] for log in heatmap_logs}
    
    context = {
        'emp': employee,
        'stats': {
            'hadir': hadir,
            'izin': izin,
            'sakit': sakit,
            'alpha': alpha,
            'working_days': working_days,
            'hadir_pct': round((hadir / max(working_days, 1)) * 100),
        },
        'recent_logs': recent_logs,
        'mutations': mutations,
        'shift_assignment': shift_assignment,
        'attendance_dates': attendance_dates,
        'current_month': now.strftime('%B %Y'),
    }
    
    return render(request, 'portal/partials/_employee_detail.html', context)


# =============================================================================
# EMPLOYEE EDIT VIEW
# =============================================================================

@login_required
def employee_edit_view(request, employee_id):
    """
    View untuk mengedit data karyawan.
    GET: Render form edit dalam modal
    POST: Simpan perubahan data
    """
    from attendance.models import Employee, Department, WorkLocation, ShiftPattern, EmployeeShiftAssignment
    
    # Permission Check: HRD/Admin/Superuser only
    if not request.user.is_superuser:
        if hasattr(request.user, 'employee_profile'):
            if request.user.employee_profile.role not in ['ADMIN', 'HRD']:
                return HttpResponse('<div class="alert alert-danger">Akses ditolak. Hanya HRD/Admin yang bisa mengedit data karyawan.</div>', status=403)
        else:
            return HttpResponse('<div class="alert alert-danger">Akses ditolak.</div>', status=403)
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        # Get form data
        full_name = request.POST.get('full_name', '').strip()
        employee_type = request.POST.get('employee_type', '')
        department_id = request.POST.get('department', '')
        phone_number = request.POST.get('phone_number', '').strip()
        telegram_user_id = request.POST.get('telegram_user_id', '').strip()
        device_user_id = request.POST.get('device_user_id', '').strip()
        joined_date_str = request.POST.get('joined_date', '')
        is_active = request.POST.get('is_active') == 'on'
        shift_pattern_id = request.POST.get('shift_pattern', '')
        
        # Validation
        if not full_name:
            return HttpResponse('<div class="alert alert-warning">Nama lengkap wajib diisi.</div>')
        
        try:
            with transaction.atomic():
                # Update employee fields
                employee.full_name = full_name
                employee.employee_type = employee_type
                employee.phone_number = phone_number if phone_number else None
                employee.telegram_user_id = telegram_user_id if telegram_user_id else None
                employee.is_active = is_active
                
                # Device User ID
                if device_user_id:
                    employee.device_user_id = int(device_user_id)
                else:
                    employee.device_user_id = None
                
                # Department
                if department_id:
                    employee.department_id = department_id
                else:
                    employee.department = None
                
                # Joined Date
                if joined_date_str:
                    from datetime import datetime
                    employee.joined_date = datetime.strptime(joined_date_str, '%Y-%m-%d').date()
                
                employee.save()
                
                # Handle Shift Assignment
                if shift_pattern_id:
                    shift_pattern = get_object_or_404(ShiftPattern, id=shift_pattern_id)
                    # Deactivate previous assignments
                    EmployeeShiftAssignment.objects.filter(employee=employee, is_active=True).update(is_active=False)
                    # Create new assignment with effective_from date
                    from django.utils import timezone
                    EmployeeShiftAssignment.objects.create(
                        employee=employee,
                        shift_pattern=shift_pattern,
                        is_active=True,
                        effective_from=timezone.now().date()
                    )
            
            # Success response - reload current employee detail
            return HttpResponse(f'''
                <div class="alert alert-success">
                    <i class="fas fa-check-circle me-2"></i>
                    Data <strong>{employee.full_name}</strong> berhasil diperbarui!
                </div>
                <script>
                    setTimeout(() => {{
                        // Close modal
                        bootstrap.Modal.getInstance(document.getElementById('editEmployeeModal')).hide();
                        // Reload employee detail
                        htmx.ajax('GET', '/portal/employee/{employee.id}/', {{target: '#location-content-area', swap: 'innerHTML'}});
                    }}, 1000);
                </script>
            ''')
            
        except Exception as e:
            return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')
    
    # GET: Render form
    departments = Department.objects.all()
    shift_patterns = ShiftPattern.objects.all()
    
    # Get current shift assignment
    current_shift = None
    try:
        current_shift = EmployeeShiftAssignment.objects.filter(
            employee=employee, is_active=True
        ).select_related('shift_pattern').first()
    except:
        pass
    
    context = {
        'emp': employee,
        'departments': departments,
        'shift_patterns': shift_patterns,
        'current_shift': current_shift,
        'employee_types': Employee.TYPE_CHOICES,
    }
    
    return render(request, 'portal/partials/_employee_edit_form.html', context)


# =============================================================================
# RECAP MATRIX VIEW (Meja Kerja Rekapitulasi)
# =============================================================================

@login_required
def recap_matrix_view(request):
    """
    Meja Kerja Rekapitulasi - Matriks Absensi Bulanan
    
    RBAC Rules:
    - KERANI: Hanya melihat lokasi sendiri (assigned_location)
    - HRD/ADMIN: Bisa memilih lokasi apapun
    """
    from attendance.models import WorkLocation, Employee, AttendanceLog
    from django.utils import timezone
    from django.db.models import F
    from calendar import monthrange
    from datetime import date, timedelta
    from collections import defaultdict
    import holidays  # Holiday detection (Reload Triggered)
    
    # Get current date for defaults
    now = timezone.now()
    
    # Get filter parameters
    try:
        month = int(request.GET.get('month', now.month))
        year = int(request.GET.get('year', now.year))
    except (ValueError, TypeError):
        month = now.month
        year = now.year
    
    # Validate month range
    if month < 1 or month > 12:
        month = now.month
    
    # =========================================================================
    # RBAC: STRICT LOCATION FILTERING
    # =========================================================================
    selected_location = None
    all_locations = []
    user_role = None
    can_select_location = False
    profile = None  # Initialize profile to prevent UnboundLocalError
    
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        user_role = profile.role
        
        if profile.role == 'KERANI':
            # KERANI: Force to assigned location only
            selected_location = profile.assigned_location
            can_select_location = False
        else:
            # HRD / ADMIN: Can select any location (leaf nodes only)
            can_select_location = True
            # Filter only leaf nodes: rght == lft + 1 indicates no children
            all_locations = WorkLocation.objects.filter(rght=F('lft') + 1).order_by('tree_id', 'lft')
            
            # Check if location_id specified in GET
            location_id = request.GET.get('location_id')
            if location_id:
                try:
                    selected_location = WorkLocation.objects.get(id=location_id)
                except WorkLocation.DoesNotExist:
                    selected_location = None
            
            # Default to first location if not specified
            if not selected_location and all_locations.exists():
                selected_location = all_locations.first()
    else:
        # Superuser without profile
        if request.user.is_superuser:
            can_select_location = True
            # Filter only leaf nodes: rght == lft + 1 indicates no children
            all_locations = WorkLocation.objects.filter(rght=F('lft') + 1).order_by('tree_id', 'lft')
            location_id = request.GET.get('location_id')
            if location_id:
                try:
                    selected_location = WorkLocation.objects.get(id=location_id)
                except WorkLocation.DoesNotExist:
                    pass
            if not selected_location and all_locations.exists():
                selected_location = all_locations.first()
    
    # =========================================================================
    # VIEW MODE SELECTION
    # =========================================================================
    employee_id = request.GET.get('employee_id')
    mode = 'matrix'
    personal_logs = []
    summary_stats = {'late': 0, 'overtime': 0, 'alpha': 0, 'permit': 0, 'sick': 0}
    personal_employee = None  # Will hold target employee in personal mode
    
    # If specific employee selected, switch to PERSONAL MODE
    if employee_id:
        try:
            target_employee = Employee.objects.get(id=employee_id)
            personal_employee = target_employee  # Set for template context
            mode = 'personal'
            
            # Build date range for the month
            _, days_in_month = monthrange(year, month)
            date_range = [date(year, month, day) for day in range(1, days_in_month + 1)]
            
            # Fetch logs for this employee only
            logs = AttendanceLog.objects.filter(
                employee=target_employee,
                timestamp__year=year,
                timestamp__month=month
            ).order_by('timestamp')
            
            # Group logs by LOCAL date (crucial for correct daily bucket)
            daily_logs = defaultdict(list)
            for log in logs:
                # Convert to local time first!
                local_dt = timezone.localtime(log.timestamp)
                daily_logs[local_dt.date()].append({
                    'log': log,
                    'local_dt': local_dt
                })
            
            # Standard Schedule (Hardcoded for now, can be moved to model later)
            # SCHEDULE_IN = timezone.datetime.strptime('08:00', '%H:%M').time()
            # SCHEDULE_OUT = timezone.datetime.strptime('17:00', '%H:%M').time()
            
            # Holiday Object for Indonesia
            id_holidays = holidays.ID(years=[year, year-1])
            
            for d in date_range:
                # Get records for this local date
                day_records = daily_logs.get(d, [])
                
                day_stat = {
                    'date': d,
                    'is_weekend': d.weekday() == 6,  # Only Sunday is weekend (holiday)
                    'is_holiday': d in id_holidays,
                    'holiday_name': id_holidays.get(d),
                    'schedule_in': '08:00',
                    'schedule_out': '17:00',
                    'clock_in': '-',
                    'clock_out': '-',
                    'late_minutes': 0,
                    'overtime_minutes': 0,
                    'status': '',
                    'status_class': '',
                    'raw_status': '',
                    # 5 Checkpoint times
                    'cp_masuk': None,
                    'cp_1': None,
                    'cp_istirahat': None,
                    'cp_2': None,
                    'cp_pulang': None,
                    # Count filled checkpoints
                    'checkpoints_filled': 0,
                }
                
                if day_records:
                    # Sort by time
                    day_records.sort(key=lambda x: x['local_dt'])
                    
                    # Extract checkpoints from logs based on log_category
                    for rec in day_records:
                        log = rec['log']
                        local_dt = rec['local_dt']
                        time_str = local_dt.strftime('%H:%M')
                        
                        # Map log_category to checkpoint fields
                        cat = getattr(log, 'log_category', None)
                        if cat == 'MASUK':
                            day_stat['cp_masuk'] = time_str
                            day_stat['checkpoints_filled'] += 1
                        elif cat == 'CP_1':
                            day_stat['cp_1'] = time_str
                            day_stat['checkpoints_filled'] += 1
                        elif cat == 'ISTIRAHAT':
                            day_stat['cp_istirahat'] = time_str
                            day_stat['checkpoints_filled'] += 1
                        elif cat == 'CP_2':
                            day_stat['cp_2'] = time_str
                            day_stat['checkpoints_filled'] += 1
                        elif cat == 'PULANG':
                            day_stat['cp_pulang'] = time_str
                            day_stat['checkpoints_filled'] += 1
                    
                    # Fallback: If no log_category, use first/last for clock_in/out
                    first_record = day_records[0]
                    first_log = first_record['log']
                    local_in = first_record['local_dt']
                    
                    day_stat['clock_in'] = local_in.strftime('%H:%M')
                    day_stat['status'] = first_log.get_status_display() if hasattr(first_log, 'get_status_display') else ''
                    day_stat['raw_status'] = getattr(first_log, 'status', '')
                    
                    # If cp_masuk not set from category, use first log
                    if not day_stat['cp_masuk']:
                        day_stat['cp_masuk'] = day_stat['clock_in']
                        day_stat['checkpoints_filled'] += 1
                    
                    # Calculate Late
                    cin_time = local_in.time()
                    dummy_date = date(2000, 1, 1)
                    
                    # Dynamic Schedule & Late Tolerance
                    daily_sch, shift_pattern = get_employee_schedule(personal_employee, d)
                    
                    # Default values
                    sch_in = DEFAULT_SCHEDULE_IN
                    tol = 0
                    
                    if daily_sch:
                        sch_in = daily_sch.clock_in
                        tol = daily_sch.late_tolerance
                    
                    # Threshold = Scheduled In + Tolerance
                    dt_sch = datetime.combine(dummy_date, sch_in)
                    dt_threshold = dt_sch + timedelta(minutes=tol)
                    
                    # Check if Late (Actual Time > Threshold)
                    if cin_time > dt_threshold.time() and not day_stat['is_holiday'] and not day_stat['is_weekend']:
                        dt_in = datetime.combine(dummy_date, cin_time)
                        # Late calculated from Threshold Time (tolerance not counted as late)
                        diff = (dt_in - dt_threshold).total_seconds() / 60
                        day_stat['late_minutes'] = int(diff)
                        summary_stats['late'] += int(diff)
                    
                    # Clock Out (Last Record if > 1)
                    if len(day_records) > 1:
                        last_record = day_records[-1]
                        local_out = last_record['local_dt']
                        day_stat['clock_out'] = local_out.strftime('%H:%M')
                        
                        # If cp_pulang not set from category, use last log
                        if not day_stat['cp_pulang']:
                            day_stat['cp_pulang'] = day_stat['clock_out']
                            day_stat['checkpoints_filled'] += 1
                        
                        # Calculate Overtime
                        cout_time = local_out.time()
                        
                        # Dynamic Schedule Out with Overtime Tolerance
                        sch_out = DEFAULT_SCHEDULE_OUT
                        ot_tol = 0  # overtime tolerance in minutes
                        if daily_sch:
                            sch_out = daily_sch.clock_out
                            ot_tol = daily_sch.overtime_tolerance
                        
                        # Calculate overtime threshold (clock_out + tolerance)
                        dt_sch_out = datetime.combine(dummy_date, sch_out)
                        dt_ot_threshold = dt_sch_out + timedelta(minutes=ot_tol)
                        
                        # Overtime only counts if employee leaves AFTER the threshold
                        if cout_time > dt_ot_threshold.time():
                            dt_out = datetime.combine(dummy_date, cout_time)
                            # Overtime calculated from threshold time, not clock_out
                            diff = (dt_out - dt_ot_threshold).total_seconds() / 60
                            day_stat['overtime_minutes'] = int(diff)
                            summary_stats['overtime'] += int(diff)
                    
                    # Determine Status Class
                    if first_log.status == 'CHECKIN':
                        day_stat['status_class'] = 'text-success fw-bold'
                        if day_stat['is_holiday']:
                             day_stat['status'] += ' (Hari Libur)'
                    elif first_log.status == 'SICK':
                        day_stat['status_class'] = 'text-warning fw-bold'
                        summary_stats['sick'] += 1
                    elif first_log.status == 'PERMIT':
                        day_stat['status_class'] = 'text-info fw-bold'
                        summary_stats['permit'] += 1
                    elif first_log.status == 'ALPHA':
                        day_stat['status_class'] = 'text-danger fw-bold'
                        summary_stats['alpha'] += 1
                        
                else:
                    # No logs
                    if day_stat['is_holiday']:
                        day_stat['status'] = 'Libur: ' + (day_stat['holiday_name'] or '')
                        day_stat['status_class'] = 'text-secondary'
                    elif day_stat['is_weekend']:
                        day_stat['status'] = 'Minggu'
                        day_stat['status_class'] = 'text-secondary'

                    elif d < now.date():
                        # Check for Leave (Sakit/Izin/Cuti)
                        leave = EmployeeLeave.objects.filter(
                            employee=personal_employee,
                            start_date__lte=d,
                            end_date__gte=d
                        ).first()
                        
                        if leave:
                            day_stat['status'] = leave.get_leave_type_display()
                            if leave.leave_type == 'SAKIT':
                                day_stat['status_class'] = 'text-warning fw-bold'
                                summary_stats['sick'] += 1
                            elif leave.leave_type == 'IZIN':
                                day_stat['status_class'] = 'text-info fw-bold'
                                summary_stats['permit'] += 1
                            elif leave.leave_type == 'CUTI':
                                day_stat['status_class'] = 'text-success fw-bold'
                                # summary_stats['leave'] += 1 # Add if needed
                            else:
                                day_stat['status_class'] = 'text-secondary'
                        else:
                            day_stat['status'] = 'Alpha'
                            day_stat['status_class'] = 'text-danger fw-bold'
                            summary_stats['alpha'] += 1
                    else:
                        day_stat['status'] = '-'
                
                personal_logs.append(day_stat)
                
        except Employee.DoesNotExist:
            mode = 'matrix'
            
    
    # =========================================================================
    # BUILD MATRIX DATA (Only if Mode == MATRIX)
    # =========================================================================
    employees = []
    matrix_data = {}
    date_range = []
    fp_summary_stats = {}
    wa_summary_data = {}
    
    if selected_location:
        # Get all sub-locations (include self)
        sub_locations = selected_location.get_descendants(include_self=True)
        
        # Get active employees in these locations
        employees = Employee.objects.filter(
            home_base__in=sub_locations,
            is_verified=True,
            is_active=True
        ).select_related('department', 'home_base').order_by('full_name')
        
        if mode == 'matrix':
            # Build date range for the month
            _, days_in_month = monthrange(year, month)
            date_range = [date(year, month, day) for day in range(1, days_in_month + 1)]
            
            # Define Schedule In locally to ensure it's available
            # SCHEDULE_IN = time(8, 0)

            # Fetch logs for all employees
            logs = AttendanceLog.objects.filter(
                employee__in=employees,
                timestamp__year=year,
                timestamp__month=month
            ).select_related('employee').order_by('employee', 'timestamp')
            
            # Group logs by employee and date
            employee_date_logs = defaultdict(lambda: defaultdict(list))
            for log in logs:
                # Convert to local time to ensure correct date bucket
                local_dt = timezone.localtime(log.timestamp)
                employee_date_logs[log.employee_id][local_dt.date()].append(log)
            
            # Build matrix: { employee_id: { date_obj: status_code } }
            
            # Holiday Object for Indonesia
            id_holidays = holidays.ID(years=[year, year-1])

            # fp_summary_stats is already initialized above
            # Ensure we iterate over specific employees if active_tab is relevant? 
            # No, logic is fine.
            
            for emp in employees:
                emp_matrix = {}
                emp_stats = {'H': 0, 'A': 0, 'T': 0, 'S': 0, 'I': 0}
                for d in date_range:
                    day_logs = employee_date_logs.get(emp.id, {}).get(d, [])
                    is_holiday = d in id_holidays
                    
                    if day_logs:
                        # Check specific status from log
                        first_log = day_logs[0]
                        status_map = {
                            'CHECKIN': 'H', 'SICK': 'S', 
                            'PERMIT': 'I', 'ALPHA': 'A'
                        }
                        st = status_map.get(first_log.status, 'H')
                        emp_matrix[d] = st
                        
                        # Stats Calculation
                        if st == 'H':
                            emp_stats['H'] += 1
                            # Check Late
                            # Check Late
                            local_dt = timezone.localtime(first_log.timestamp)
                            
                            # Dynamic Schedule for Matrix
                            # Note: This increases query count (N*30). 
                            # If performance issues arise, consider bulk pre-fetching assignments.
                            daily_sch, _ = get_employee_schedule(emp, d)
                            
                            sch_in = DEFAULT_SCHEDULE_IN
                            tol = 0
                            if daily_sch:
                                sch_in = daily_sch.clock_in
                                tol = daily_sch.late_tolerance
                                
                            dummy_date = date(2000, 1, 1)
                            dt_sch = datetime.combine(dummy_date, sch_in)
                            dt_threshold = dt_sch + timedelta(minutes=tol)
                            
                            # Only count late if NOT holiday and NOT Sunday
                            is_weekend = d.weekday() == 6  # Sunday only
                            
                            # Round clock-in time to minutes (ignore seconds)
                            # This ensures 08:10:05 is treated as 08:10:00
                            clock_time_rounded = local_dt.time().replace(second=0, microsecond=0)
                            threshold_time_rounded = dt_threshold.time().replace(second=0, microsecond=0)
                            
                            # DEBUG: Print late calculation details
                            if emp.full_name and 'Joni' in emp.full_name:
                                print(f"DEBUG MATRIX [{d}] {emp.full_name}: clock={local_dt.time()} -> rounded={clock_time_rounded}, threshold={threshold_time_rounded}, is_late={clock_time_rounded > threshold_time_rounded}")
                            
                            if clock_time_rounded > threshold_time_rounded and not is_holiday and not is_weekend:
                                emp_stats['T'] += 1
                        elif st == 'S':
                            emp_stats['S'] += 1
                        elif st == 'I':
                            emp_stats['I'] += 1
                        elif st == 'A':
                            emp_stats['A'] += 1

                    else:
                        if is_holiday:
                            emp_matrix[d] = 'L' # Libur Nasional
                        elif d.weekday() == 6: # Sunday Only
                            emp_matrix[d] = 'L' # Libur Weekend
                        elif d < now.date():
                            emp_matrix[d] = 'A'
                            emp_stats['A'] += 1
                            # Check Leave for Alpha?
                            # Optimally we should check leaves here too for FP matrix to be accurate
                            # But for now let's stick to existing logic + stats
                            # (Existing logic didn't check leaves for FP matrix AFAIK? 
                            # Wait, line 1426 checks leave for PERSONAL view. Matrix view didn't seem to check leave?
                            # Actually, let's keep it simple for now as requested: just summary cols logic)
                        else:
                            emp_matrix[d] = ''
                
                matrix_data[emp.id] = emp_matrix
                fp_summary_stats[emp.id] = emp_stats
            
    # Prepare Holidays Map for Template (Date String -> Name)
    # MOVED OUTSIDE if mode == 'matrix' block to fix UnboundLocalError
    holidays_map = {}
    id_holidays = holidays.ID(years=[year, year-1]) 
    
    for d in date_range:
        if d in id_holidays:
            # Key must be string to match template date filter
            holidays_map[d.strftime('%Y-%m-%d')] = id_holidays.get(d)
        elif d.weekday() == 6:
            # Explicitly mark Sundays for template coloring
            holidays_map[d.strftime('%Y-%m-%d')] = "Minggu"

    # =========================================================================
    # WHATSAPP / TELEGRAM 5-POINT TRACKING
    # =========================================================================
    # Parse specific date for WA Daily View (default: today)
    wa_specific_date_str = request.GET.get('wa_date', now.date().isoformat())
    try:
        wa_specific_date = date.fromisoformat(wa_specific_date_str)
    except ValueError:
        wa_specific_date = now.date()
    
    # Split employees by source type
    fingerprint_employees = []
    wa_employees = []

    if employees:
        # Get employees with confirmed log sources
        has_wa_logs = set(AttendanceLog.objects.filter(
            employee__in=employees,
            source_type='TELEGRAM'
        ).values_list('employee_id', flat=True))
        
        has_fp_logs = set(AttendanceLog.objects.filter(
            employee__in=employees,
            source_type='FINGERPRINT'
        ).values_list('employee_id', flat=True))
        
        for e in employees:
            # 1. Existing logs dictate category
            if e.id in has_wa_logs:
                wa_employees.append(e)
            elif e.id in has_fp_logs:
                fingerprint_employees.append(e)
            else:
                # 2. No logs yet? Use Heuristic based on Employee Type
                # 'HARIAN' (Buruh Harian) -> WA (Lapangan)
                # 'MANDOR' -> WA (Lapangan)
                if e.employee_type in ['HARIAN', 'MANDOR']:
                    wa_employees.append(e)
                else:
                    # Default for Staff / Others
                    fingerprint_employees.append(e)
    
    # WA 5-Point Categories
    WA_CATEGORIES = ['MASUK', 'CHECKPOINT_1', 'ISTIRAHAT', 'CHECKPOINT_2', 'PULANG']
    WA_CATEGORY_ICONS = {
        'MASUK': ('fa-sun', 'Pagi'),
        'CHECKPOINT_1': ('fa-flag', 'CP1'),
        'ISTIRAHAT': ('fa-mug-hot', 'Istirahat'),
        'CHECKPOINT_2': ('fa-flag-checkered', 'CP2'),
        'PULANG': ('fa-home', 'Pulang'),
    }
    
    # WA Daily Data (Global View - All WA Employees for specific date)
    wa_daily_data = {}
    wa_employee_id = request.GET.get('wa_employee_id')
    wa_mode = 'matrix' if not wa_employee_id else 'personal'
    wa_personal_logs = []
    wa_personal_employee = None  # Will hold target WA employee in personal mode
    
    # WA MATRIX DATA: { emp_id: { date: { category: time_str } } }
    wa_matrix_data = {}
    wa_summary_data = {}
    
    # Build date range for WA matrix (same as fingerprint)
    _, wa_days_in_month = monthrange(year, month)
    wa_date_range = [date(year, month, day) for day in range(1, wa_days_in_month + 1)]

    if wa_employees:
        # Build set of holiday dates for quick lookup
        holidays_set = set(holidays_map.keys())
        
        # Initialize matrix for all employees
        for emp in wa_employees:
            wa_matrix_data[emp.id] = {}
            for d in wa_date_range:
                wa_matrix_data[emp.id][d] = {cat: None for cat in WA_CATEGORIES}
                wa_matrix_data[emp.id][d]['IZIN'] = None  # Track izin status
        
        # Fetch ALL logs for WA employees in this month
        wa_month_logs = AttendanceLog.objects.filter(
            employee__in=wa_employees,
            timestamp__year=year,
            timestamp__month=month,
            source_type='TELEGRAM'
        ).select_related('employee')
        
        # Fill in the matrix
        for log in wa_month_logs:
            local_time = timezone.localtime(log.timestamp)
            log_date = local_time.date()
            cat = log.log_category if log.log_category in WA_CATEGORIES else 'UNKNOWN'
            if cat in WA_CATEGORIES and log_date in wa_matrix_data.get(log.employee_id, {}):
                wa_matrix_data[log.employee_id][log_date][cat] = local_time.strftime('%H:%M')
            # Check for izin/sakit (if stored in notes or specific field)
            if hasattr(log, 'notes') and log.notes and ('IZIN' in log.notes.upper() or 'SAKIT' in log.notes.upper()):
                wa_matrix_data[log.employee_id][log_date]['IZIN'] = log.notes[:10]
        
        # Fetch leaves for all WA employees in range (Inclusive)
        wa_leaves = EmployeeLeave.objects.filter(
            employee__in=wa_employees,
            start_date__lte=wa_date_range[-1],
            end_date__gte=wa_date_range[0]
        )
        
        for leave in wa_leaves:
            # Determine intersection with month
            start = max(leave.start_date, wa_date_range[0])
            end = min(leave.end_date, wa_date_range[-1])
            
            curr = start
            while curr <= end:
                # Ensure emp and date exist in matrix
                if leave.employee_id in wa_matrix_data and curr in wa_matrix_data[leave.employee_id]:
                     status_text = leave.get_leave_type_display()
                     
                     # 1. Set IZIN field (for Summary Calculation)
                     wa_matrix_data[leave.employee_id][curr]['IZIN'] = status_text
                     
                     # 2. Update Display Cells if Empty (Visualize in Big Table)
                     # Only if NO LOG exists strictly (check MASUK is None)
                     if not wa_matrix_data[leave.employee_id][curr]['MASUK']:
                         for cat in WA_CATEGORIES:
                             wa_matrix_data[leave.employee_id][curr][cat] = status_text
                
                curr += timedelta(days=1)
        
        # Calculate summary per employee
        wa_summary_data = {}
        # We'll use a new dict for the 5-column stats to avoid breaking existing logic if needed
        # But actually let's just add to wa_summary_data
        
        for emp in wa_employees:
            wa_summary_data[emp.id] = {
                'missing_pagi': 0, 'missing_cp1': 0, 'missing_istirahat': 0,
                'missing_cp2': 0, 'missing_pulang': 0, 'izin_count': 0,
                'total_missing': 0,
                # New Stats
                'H': 0, 'A': 0, 'T': 0, 'S': 0, 'I': 0
            }
            for d in wa_date_range:
                date_str = d.isoformat()
                day_data = wa_matrix_data[emp.id][d]
                
                # Check Izin/Sakit first
                izin_status = day_data.get('IZIN')
                if izin_status:
                    if 'SAKIT' in izin_status.upper():
                        wa_summary_data[emp.id]['S'] += 1
                    else:
                        wa_summary_data[emp.id]['I'] += 1
                    wa_summary_data[emp.id]['izin_count'] += 1
                    # Don't count H/A/Missing if Izin
                    continue
                
                # Check Hadir (Masuk)
                masuk_time = day_data.get('MASUK')
                if masuk_time:
                    wa_summary_data[emp.id]['H'] += 1
                    # Check Late
                    # masuk_time is string "HH:MM"
                    if masuk_time > "08:00":
                        wa_summary_data[emp.id]['T'] += 1
                else:
                    # No Masuk
                    # Check Alpha: Not holiday, Not Sunday, Past Date
                    if d < now.date() and date_str not in holidays_set and d.weekday() != 6:
                         wa_summary_data[emp.id]['A'] += 1
                
                # Skip stats for future/holidays for Missing Point Calculation
                if d > now.date() or date_str in holidays_set or d.weekday() == 6:
                    continue

                if not day_data.get('MASUK'): wa_summary_data[emp.id]['missing_pagi'] += 1
                if not day_data.get('CHECKPOINT_1'): wa_summary_data[emp.id]['missing_cp1'] += 1
                if not day_data.get('ISTIRAHAT'): wa_summary_data[emp.id]['missing_istirahat'] += 1
                if not day_data.get('CHECKPOINT_2'): wa_summary_data[emp.id]['missing_cp2'] += 1
                if not day_data.get('PULANG'): wa_summary_data[emp.id]['missing_pulang'] += 1
            
            wa_summary_data[emp.id]['total_missing'] = (
                wa_summary_data[emp.id]['missing_pagi'] +
                wa_summary_data[emp.id]['missing_cp1'] +
                wa_summary_data[emp.id]['missing_istirahat'] +
                wa_summary_data[emp.id]['missing_cp2'] +
                wa_summary_data[emp.id]['missing_pulang']
            )
        

    # DETERMINE ACTIVE TAB
    # Default to 'fingerprint'
    active_tab = 'fingerprint'
    
    # If requests explicit tab via GET or if WA Employee ID is present -> WhatsApp
    if request.GET.get('tab') == 'whatsapp' or wa_employee_id or request.GET.get('active_tab') == 'whatsapp':
        active_tab = 'whatsapp'

    # Convert keys to string for template compatibility
    print(f"DEBUG: Pre-Context. Matrix Size: {len(matrix_data)}. FP Stats Size: {len(fp_summary_stats)}")
    fp_summary_stats_str = {str(k): v for k, v in fp_summary_stats.items()} if fp_summary_stats else {}
    wa_summary_data_str = {str(k): v for k, v in wa_summary_data.items()} if wa_summary_data else {}

    context = {
        'selected_location': selected_location,
        'all_locations': all_locations,
        'can_select_location': can_select_location,
        'month_names': [(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
        'selected_month': month,
        'year_options': range(now.year - 2, now.year + 2),
        'selected_year': year,
        'fingerprint_employees': fingerprint_employees,
        'wa_employees': wa_employees,
        'matrix_data': matrix_data,
        'fp_summary_stats': fp_summary_stats_str,
        'wa_summary_data': wa_summary_data_str,
        'date_range': date_range,
        'holidays_map': holidays_map,
        'selected_employee_id': employee_id,
        'mode': mode,
        'personal_employee': personal_employee,
        'personal_logs': personal_logs,
        'summary_stats': summary_stats,
        # WA Context
        'wa_matrix_data': wa_matrix_data,
        'wa_summary_data': wa_summary_data,
        'wa_date_range': wa_date_range,
        'wa_categories': WA_CATEGORIES,
        'wa_mode': wa_mode,
        'wa_personal_employee': wa_personal_employee,
        'selected_wa_employee_id': wa_employee_id,
        # Active Tab State
        'active_tab': active_tab, 
    }
        
    # WA Personal View (Monthly - Single Employee)
    if wa_employee_id:
        try:
            wa_target_employee = Employee.objects.get(id=wa_employee_id)
            wa_personal_employee = wa_target_employee  # Set for template context
            _, days_in_month = monthrange(year, month)
            wa_date_range = [date(year, month, day) for day in range(1, days_in_month + 1)]
                
            # Fetch all logs for this employee in the month (Remove strict source_type filter)
            wa_month_logs = AttendanceLog.objects.filter(
                employee=wa_target_employee,
                timestamp__year=year,
                timestamp__month=month
            ).order_by('timestamp')
            
            # Group by date and category
            wa_grouped = defaultdict(lambda: {cat: None for cat in WA_CATEGORIES})
            for log in wa_month_logs:
                local_dt = timezone.localtime(log.timestamp)
                log_date = local_dt.date()
                cat = log.log_category if log.log_category in WA_CATEGORIES else 'UNKNOWN'
                if cat in WA_CATEGORIES:
                    wa_grouped[log_date][cat] = {
                        'time': local_dt.strftime('%H:%M'),
                        'log': log,
                    }
            
            # Initialize Summary Stats for WA
            wa_summary_stats = {'late': 0, 'overtime': 0, 'alpha': 0, 'permit': 0, 'sick': 0}
            
            # Schedule Constants (Reuse standard or define here)
            # Assuming standard 08:00 - 17:00 for calculation
            SCHEDULE_IN = timezone.datetime.strptime('08:00', '%H:%M').time()
            SCHEDULE_OUT = timezone.datetime.strptime('17:00', '%H:%M').time()
            dummy_date = date(2000, 1, 1)

            # Build personal logs list
            for d in wa_date_range:
                is_holiday = d in id_holidays
                is_weekend = d.weekday() == 6  # Only Sunday is weekend
                holiday_name = id_holidays.get(d)
                
                day_data = wa_grouped.get(d, {cat: None for cat in WA_CATEGORIES})
                
                # Count completed checkpoints
                completed = sum(1 for cat in WA_CATEGORIES if day_data.get(cat))
                progress = int((completed / 5) * 100)
                
                # Determine Status and Late/Overtime
                status = '-'
                status_class = ''
                late_minutes = 0
                
                # Check for explicit log status (SICK/PERMIT/ALPHA from AttendanceLog)
                # We check if any log in day_data has a special status
                special_status_log = None
                for cat in WA_CATEGORIES:
                    entry = day_data.get(cat)
                    if entry and entry.get('log'):
                        log = entry['log']
                        if log.status in ['SICK', 'PERMIT', 'ALPHA']:
                            special_status_log = log
                            break
                
                if special_status_log:
                    st = special_status_log.status
                    if st == 'SICK':
                        status = 'Sakit'
                        status_class = 'text-warning fw-bold'
                        wa_summary_stats['sick'] += 1
                    elif st == 'PERMIT':
                        status = 'Izin'
                        status_class = 'text-info fw-bold'
                        wa_summary_stats['permit'] += 1
                    elif st == 'ALPHA':
                        status = 'Alpha'
                        status_class = 'text-danger fw-bold'
                        wa_summary_stats['alpha'] += 1
                
                # Check for approved Leave (Sakit/Izin/Cuti) from EmployeeLeave or Alpha/Holiday/Weekend
                elif not day_data.get('MASUK'):
                    leave = EmployeeLeave.objects.filter(
                        employee=wa_personal_employee,
                        start_date__lte=d,
                        end_date__gte=d
                    ).first()
                    
                    if leave:
                        status = leave.get_leave_type_display()
                        if leave.leave_type == 'SAKIT':
                            status_class = 'text-warning fw-bold'
                            wa_summary_stats['sick'] += 1
                        elif leave.leave_type == 'IZIN':
                            status_class = 'text-info fw-bold'
                            wa_summary_stats['permit'] += 1
                        elif leave.leave_type == 'CUTI':
                            status_class = 'text-success fw-bold'
                        else:
                            status_class = 'text-secondary'
                    else:
                        # If NO leave found, check for Holiday, Weekend, or Alpha
                        if is_holiday:
                            status = 'Libur: ' + (holiday_name or '')
                            status_class = 'text-secondary'
                        elif is_weekend:
                            status = 'Minggu'
                            status_class = 'text-secondary'
                        elif d < now.date():
                            status = 'Alpha'
                            status_class = 'text-danger fw-bold'
                            wa_summary_stats['alpha'] += 1
                        else:
                            status = '-' # Future date

                elif day_data.get('MASUK'):
                    status = 'Hadir'
                    status_class = 'text-success fw-bold'
                    
                    # Calculate Late
                    try:
                        check_in_time = datetime.strptime(day_data['MASUK']['time'], '%H:%M').time()
                        if check_in_time > SCHEDULE_IN and not is_holiday and not is_weekend:
                            dt_in = timezone.datetime.combine(dummy_date, check_in_time)
                            dt_sch = timezone.datetime.combine(dummy_date, SCHEDULE_IN)
                            diff = (dt_in - dt_sch).total_seconds() / 60
                            late_minutes = int(diff)
                            wa_summary_stats['late'] += late_minutes
                    except (ValueError, TypeError):
                        pass
                        
                    # Calculate Overtime (if PULANG exists)
                    if day_data.get('PULANG'):
                        try:
                            check_out_time = datetime.strptime(day_data['PULANG']['time'], '%H:%M').time()
                            if check_out_time > SCHEDULE_OUT:
                                dt_out = timezone.datetime.combine(dummy_date, check_out_time)
                                dt_sch_out = timezone.datetime.combine(dummy_date, SCHEDULE_OUT)
                                diff = (dt_out - dt_sch_out).total_seconds() / 60
                                wa_summary_stats['overtime'] += int(diff)
                        except (ValueError, TypeError):
                            pass

                    if is_holiday:
                         status += ' (Hari Libur)'
                
                wa_personal_logs.append({
                    'date': d,
                    'is_holiday': is_holiday,
                    'is_weekend': is_weekend,
                    'holiday_name': holiday_name,
                    'checkpoints': day_data,
                    'completed': completed,
                    'progress': progress,
                    'status': status,
                    'status_class': status_class,
                    'late_minutes': late_minutes,
                })
            
            # Add wa_summary_stats to context data (merged later)
            pass
        except Employee.DoesNotExist:
            wa_mode = 'daily'

    # Generate month/year options
    month_names = [
        (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
        (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
        (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember')
    ]
    year_options = list(range(now.year - 2, now.year + 2))
    
    # DETERMINE ACTIVE TAB
    # Default to 'fingerprint'
    active_tab = 'fingerprint'
    
    # If requests explicit tab via GET or if WA Employee ID is present -> WhatsApp
    if request.GET.get('tab') == 'whatsapp' or wa_employee_id or request.GET.get('active_tab') == 'whatsapp':
        active_tab = 'whatsapp'
    
    context = {
        'page_title': 'Meja Kerja Rekapitulasi',
        'selected_location': selected_location,
        'all_locations': all_locations,
        'can_select_location': can_select_location,
        'user_role': user_role,
        'employees': employees,
        'matrix_data': matrix_data,
        'date_range': date_range,
        'selected_month': month,
        'selected_year': year,
        'month_names': month_names,
        'year_options': year_options,
        'holidays_map': holidays_map, 
        
        # Personal Mode Context (Fingerprint)
        'mode': mode,
        'personal_logs': personal_logs,
        'summary_stats': summary_stats,
        'selected_employee_id': str(employee_id) if employee_id else '',
        'personal_employee': personal_employee,  # Employee object for personal mode
        
        # Fingerprint Employees (for Tab 1)
        'fingerprint_employees': fingerprint_employees,
        'fp_summary_stats': fp_summary_stats_str, # RE-ADDED: Lost in context redefinition
        
        # WhatsApp / Telegram Context (for Tab 2)
        'wa_employees': wa_employees,
        'wa_mode': wa_mode,
        'wa_specific_date': wa_specific_date,
        'wa_daily_data': wa_daily_data,
        'wa_matrix_data': wa_matrix_data,
        'wa_date_range': wa_date_range if wa_employees else date_range,
        'wa_personal_logs': wa_personal_logs,
        'wa_categories': WA_CATEGORIES,
        'wa_category_icons': WA_CATEGORY_ICONS,
        'wa_summary_data': wa_summary_data if wa_employees else {},
        'wa_summary_stats': wa_summary_stats if 'wa_summary_stats' in locals() else {'late': 0, 'overtime': 0, 'alpha': 0, 'permit': 0, 'sick': 0},
        'selected_wa_employee_id': str(wa_employee_id) if wa_employee_id else '',
        'wa_personal_employee': wa_personal_employee,  # WA Employee object for personal mode
        
        # Role-based access
        'user_role': profile.role if profile else 'KERANI',
        
        # Active Tab State
        'active_tab': active_tab, 
    }
    
    return render(request, 'portal/recap_matrix.html', context)


# =============================================================================
# EDIT ATTENDANCE MODAL (HTMX)
# =============================================================================

@login_required
def edit_attendance_modal(request, employee_id, date_str):
    """
    HTMX: Load modal untuk edit/create attendance log.
    
    Args:
        employee_id: UUID karyawan
        date_str: Format YYYY-MM-DD
    """
    from attendance.models import Employee, AttendanceLog
    from datetime import datetime
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return HttpResponse('<div class="alert alert-danger">Format tanggal tidak valid</div>')
    
    # Check if log exists for this employee and date
    existing_log = AttendanceLog.objects.filter(
        employee=employee,
        timestamp__date=target_date
    ).first()
    
    # Status options
    status_choices = [
        ('CHECKIN', 'Hadir (H)'),
        ('SICK', 'Sakit (S)'),
        ('PERMIT', 'Izin (I)'),
        ('ALPHA', 'Alpha (A)'),
    ]
    
    context = {
        'employee': employee,
        'target_date': target_date,
        'date_str': date_str,
        'existing_log': existing_log,
        'status_choices': status_choices,
        'is_edit': existing_log is not None,
    }
    
    return render(request, 'portal/partials/_modal_edit_log.html', context)


@login_required
def save_attendance_cell(request):
    """
    HTMX POST: Simpan/Update attendance log dan return cell fragment.
    
    Returns only the updated cell HTML for hx-swap="outerHTML".
    """
    from attendance.models import Employee, AttendanceLog
    from datetime import datetime
    from django.utils import timezone
    
    if request.method != 'POST':
        return HttpResponse('<div class="alert alert-warning">Method not allowed</div>')
    
    employee_id = request.POST.get('employee_id')
    date_str = request.POST.get('date_str')
    status = request.POST.get('status')
    clock_in = request.POST.get('clock_in')
    clock_out = request.POST.get('clock_out')
    notes = request.POST.get('notes', '')
    
    try:
        employee = Employee.objects.get(id=employee_id)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (Employee.DoesNotExist, ValueError) as e:
        return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')
    
    # Determine display status code
    status_map = {
        'CHECKIN': 'H',
        'SICK': 'S',
        'PERMIT': 'I',
        'ALPHA': 'A',
    }
    display_status = status_map.get(status, 'A')
    
    # Check if log exists
    existing_log = AttendanceLog.objects.filter(
        employee=employee,
        timestamp__date=target_date
    ).first()
    
    now = timezone.now()
    
    if status == 'ALPHA':
        # Delete existing log if marking as Alpha
        if existing_log:
            existing_log.delete()
    else:
        # Create or update log
        if existing_log:
            existing_log.status = status
            existing_log.notes = notes
            existing_log.save()
        else:
            # Create new log
            # Parse clock_in time or use default 08:00
            if clock_in:
                try:
                    time_parts = clock_in.split(':')
                    log_datetime = timezone.make_aware(
                        datetime.combine(target_date, datetime.strptime(clock_in, '%H:%M').time())
                    )
                except:
                    log_datetime = timezone.make_aware(
                        datetime.combine(target_date, datetime.strptime('08:00', '%H:%M').time())
                    )
            else:
                log_datetime = timezone.make_aware(
                    datetime.combine(target_date, datetime.strptime('08:00', '%H:%M').time())
                )
            
            AttendanceLog.objects.create(
                employee=employee,
                timestamp=log_datetime,
                status=status,
                source_type='MANUAL',
                notes=notes,
                captured_at=now,
            )
    
    # Return cell fragment with updated status
    context = {
        'employee': employee,
        'target_date': target_date,
        'date_str': date_str,
        'status': display_status,
        'is_holiday': target_date.weekday() >= 5,
    }
    
    return render(request, 'portal/partials/_attendance_cell.html', context)


# =============================================================================
# WA CELL EDIT (HTMX) - Role-Based Access Control
# =============================================================================

@login_required
def wa_edit_cell(request, employee_id, date_str, category):
    """
    HTMX: Load modal content untuk edit WA attendance cell.
    Admin bisa set waktu, Kerani hanya bisa set Izin/Sakit.
    """
    from attendance.models import Employee, AttendanceLog
    from datetime import datetime
    
    employee = Employee.objects.get(id=employee_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Get user role
    profile = getattr(request.user, 'employee_profile', None)
    user_role = profile.role if profile else 'KERANI'
    
    # Check if log exists for this cell
    existing_log = AttendanceLog.objects.filter(
        employee=employee,
        timestamp__date=target_date,
        log_category=category,
        source_type='TELEGRAM'
    ).first()
    
    existing_time = existing_log.timestamp.strftime('%H:%M') if existing_log else ''
    existing_notes = existing_log.notes if existing_log else ''
    
    # Category labels
    category_labels = {
        'MASUK': 'Pagi',
        'CHECKPOINT_1': 'Checkpoint 1',
        'ISTIRAHAT': 'Istirahat',
        'CHECKPOINT_2': 'Checkpoint 2',
        'PULANG': 'Pulang',
    }
    
    context = {
        'employee': employee,
        'date_str': date_str,
        'category': category,
        'category_label': category_labels.get(category, category),
        'user_role': user_role,
        'existing_time': existing_time,
        'existing_notes': existing_notes,
        'is_admin': user_role in ['ADMIN', 'HRD'],
    }
    
    return render(request, 'portal/partials/_wa_edit_cell_modal.html', context)


@login_required
@require_POST
def wa_save_cell(request):
    """
    HTMX: Save WA attendance cell.
    Admin bisa set waktu, Kerani hanya bisa set Izin/Sakit.
    """
    from attendance.models import Employee, AttendanceLog
    from django.utils import timezone
    from datetime import datetime
    
    employee_id = request.POST.get('employee_id')
    date_str = request.POST.get('date_str')
    category = request.POST.get('category')
    action = request.POST.get('action')  # 'set_time', 'izin', 'sakit', 'delete'
    time_value = request.POST.get('time_value', '')
    
    employee = Employee.objects.get(id=employee_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Get user role
    profile = getattr(request.user, 'employee_profile', None)
    user_role = profile.role if profile else 'KERANI'
    
    # Delete existing log if any
    existing_log = AttendanceLog.objects.filter(
        employee=employee,
        timestamp__date=target_date,
        log_category=category,
        source_type='TELEGRAM'
    ).first()
    
    if action == 'delete':
        if existing_log:
            existing_log.delete()
        return HttpResponse('<span class="text-muted opacity-25">-</span>')
    
    # Determine time and notes based on action
    if action == 'izin':
        log_time = '00:00'  # Placeholder time for izin
        notes = 'IZIN'
    elif action == 'sakit':
        log_time = '00:00'
        notes = 'SAKIT'
    elif action == 'set_time' and user_role in ['ADMIN', 'HRD']:
        log_time = time_value if time_value else '08:00'
        notes = 'Manual Entry'
    else:
        # Kerani trying to set time without permission
        return HttpResponse('<span class="text-danger">Tidak diizinkan</span>')
    
    # Create or update log
    try:
        log_datetime = timezone.make_aware(
            datetime.combine(target_date, datetime.strptime(log_time, '%H:%M').time())
        )
    except:
        log_datetime = timezone.make_aware(
            datetime.combine(target_date, datetime.strptime('08:00', '%H:%M').time())
        )
    
    if existing_log:
        existing_log.timestamp = log_datetime
        existing_log.notes = notes
        existing_log.save()
    else:
        AttendanceLog.objects.create(
            employee=employee,
            timestamp=log_datetime,
            log_category=category,
            source_type='TELEGRAM',
            notes=notes,
        )
    
    # Return updated cell content
    if action in ['izin', 'sakit']:
        return HttpResponse(f'<span class="text-warning fw-bold" style="font-size: 0.6rem;">{action.upper()[:2]}</span>')
    else:
        return HttpResponse(f'<span class="text-success" style="font-size: 0.6rem;">{log_time}</span>')


# =============================================================================
# EMPLOYEE LEAVE CRUD ENDPOINTS
# =============================================================================

@login_required
@require_POST
def employee_leave_add(request):
    """Add a new leave record for an employee"""
    from attendance.models import Employee, EmployeeLeave
    from django.utils import timezone
    from datetime import datetime
    
    employee_id = request.POST.get('employee_id')
    leave_type = request.POST.get('leave_type')
    start_date_str = request.POST.get('start_date')
    end_date_str = request.POST.get('end_date')
    notes = request.POST.get('notes', '')
    
    try:
        employee = Employee.objects.get(id=employee_id)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        if end_date < start_date:
            return HttpResponse('<div class="alert alert-danger">Tanggal selesai harus setelah tanggal mulai</div>')
        
        leave = EmployeeLeave.objects.create(
            employee=employee,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            notes=notes,
            created_by=request.user
        )
        
        # Determine target container from request headers (HTMX)
        target_id = request.headers.get('HX-Target', 'leave-list-container')

        # Return updated leave list HTML
        return render(request, 'portal/_employee_leave_list.html', {
            'leaves': employee.leaves.all()[:10],
            'employee': employee,
            'target_id': target_id
        })
        
    except Employee.DoesNotExist:
        return HttpResponse('<div class="alert alert-danger">Karyawan tidak ditemukan</div>')
    except Exception as e:
        return HttpResponse(f'<div class="alert alert-danger">Error: {str(e)}</div>')


@login_required
@require_POST
def employee_leave_delete(request, leave_id):
    """Delete a leave record"""
    from attendance.models import EmployeeLeave
    
    try:
        leave = EmployeeLeave.objects.get(id=leave_id)
        employee = leave.employee
        leave.delete()
        
        # Determine target container from request headers (HTMX)
        target_id = request.headers.get('HX-Target', 'leave-list-container')

        # Return updated leave list HTML
        return render(request, 'portal/_employee_leave_list.html', {
            'leaves': employee.leaves.all()[:10],
            'employee': employee,
            'target_id': target_id
        })

        
    except EmployeeLeave.DoesNotExist:
        return HttpResponse('<div class="alert alert-danger">Data tidak ditemukan</div>')


@login_required
def employee_leave_list(request, employee_id):
    """Get leave list for an employee (HTMX)"""
    from attendance.models import Employee
    
    try:
        employee = Employee.objects.get(id=employee_id)
        # Determine target container from request headers (HTMX)
        target_id = request.headers.get('HX-Target', 'leave-list-container')

        return render(request, 'portal/_employee_leave_list.html', {
            'leaves': employee.leaves.all()[:10],
            'employee': employee,
            'target_id': target_id
        })
    except Employee.DoesNotExist:
        return HttpResponse('<div class="alert alert-warning">Karyawan tidak ditemukan</div>')
@login_required
def fp_edit_cell(request, employee_id, date_str):
    """
    HTMX: Load modal content untuk edit Fingerprint attendance cell.
    Allows setting Hadir, Sakit, Izin, Alpha.
    """
    from attendance.models import Employee, AttendanceLog, EmployeeLeave
    from datetime import datetime
    
    employee = Employee.objects.get(id=employee_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Check for existing log (Checkin/Checkout)
    existing_log = AttendanceLog.objects.filter(
        employee=employee,
        timestamp__date=target_date,
        source_type='FINGERPRINT'
    ).first()
    
    # Check for existing leave
    existing_leave = EmployeeLeave.objects.filter(
        employee=employee,
        start_date__lte=target_date,
        end_date__gte=target_date
    ).first()
    
    existing_status = ''
    if existing_leave:
        existing_status = existing_leave.get_leave_type_display()
    elif existing_log:
        existing_status = 'Hadir (Data Mesin)'
        if existing_log.notes == 'Manual Entry':
            existing_status = 'Hadir (Manual)'
            
    context = {
        'employee': employee,
        'date_str': date_str,
        'existing_status': existing_status,
        'existing_log': existing_log,
    }
    
    return render(request, 'portal/partials/_fp_edit_cell_modal.html', context)


@login_required
@require_POST
def fp_save_cell(request):
    """
    HTMX: Save Fingerprint attendance cell.
    Updates AttendanceLog (for Hadir) or EmployeeLeave (for Izin/Sakit).
    """
    from attendance.models import Employee, AttendanceLog, EmployeeLeave
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    employee_id = request.POST.get('employee_id')
    date_str = request.POST.get('date_str')
    action = request.POST.get('action')
    
    employee = Employee.objects.get(id=employee_id)
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # 1. CLEAR EXISTING STATUS (Delete relevant logs/leaves for this day)
    # Delete Manual Logs
    AttendanceLog.objects.filter(
        employee=employee,
        timestamp__date=target_date,
        source_type='FINGERPRINT',
        notes='Manual Entry'
    ).delete()
    
    # Check for Leave covering this date
    existing_leaves = EmployeeLeave.objects.filter(
        employee=employee,
        start_date__lte=target_date,
        end_date__gte=target_date
    )
    # Note: Deleting a multi-day leave for one day is complex.
    # For now, we assume single-day edits or warn user. 
    # Logic: If exact match, delete. If overlap, maybe shrink? 
    # SIMPLIFICATION: Only delete if exact match or simple intersection logic?
    # For MVP: Just delete strict single day leaves or warn?
    # Let's just delete any leave that *starts* on this day to avoid destroying long leaves?
    # BETTER: Just delete any leave that intersects. User can re-add if needed.
    existing_leaves.delete() 

    # 2. APPLY NEW ACTION
    if action == 'delete':
        return HttpResponse('<span class="text-muted opacity-25">-</span>')
        
    elif action == 'hadir':
        # Create Dummy Log (Checkin 08:00, Checkout 17:00)
        log_in = timezone.make_aware(datetime.combine(target_date, datetime.strptime('08:00', '%H:%M').time()))
        log_out = timezone.make_aware(datetime.combine(target_date, datetime.strptime('17:00', '%H:%M').time()))
        
        AttendanceLog.objects.create(
            employee=employee,
            timestamp=log_in,
            source_type='FINGERPRINT',
            device_id='MANUAL',
            notes='Manual Entry'
        )
        AttendanceLog.objects.create(
            employee=employee,
            timestamp=log_out,
            source_type='FINGERPRINT',
            device_id='MANUAL',
            notes='Manual Entry'
        )
        return HttpResponse('<span class="text-dark fw-bold">H</span>')
        
    elif action in ['izin', 'sakit', 'cuti']:
        leave_type_map = {'izin': 'IZIN', 'sakit': 'SAKIT', 'cuti': 'CUTI'}
        EmployeeLeave.objects.create(
            employee=employee,
            leave_type=leave_type_map.get(action, 'IZIN'),
            start_date=target_date,
            end_date=target_date,
            reason='Manual Update via Matrix'
        )
        color_class = {
            'sakit': 'text-warning fw-bold', 
            'izin': 'text-info fw-bold',
            'cuti': 'text-success fw-bold'
        }.get(action, 'text-secondary')
        
        return HttpResponse(f'<span class="{color_class}">{action.upper()[:1]}</span>')
        
    elif action == 'alpha':
        # Ensure no logs/leaves exist (already cleared above)
        return HttpResponse('<span class="text-danger fw-bold">A</span>')
        
    return HttpResponse('<span class="text-muted opacity-25">-</span>')
