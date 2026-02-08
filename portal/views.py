from django.shortcuts import render
from django.contrib.auth.decorators import login_required

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
    
    locations = WorkLocation.objects.all()
    
    # RBAC: Kerani only sees their location and descendants
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location:
            # get_descendants(include_self=True) handles the tree traversal efficiently
            locations = profile.assigned_location.get_descendants(include_self=True)
            
    context = {
        'page_title': 'Pusat Data Wilayah',
        'locations': locations,
    }
    return render(request, 'portal/tree_explorer.html', context)


@login_required
def location_detail_view(request, location_id):
    """
    HTMX: Load detail konten untuk panel kanan Tree Explorer
    """
    from attendance.models import WorkLocation, Employee, AttendanceLog
    from django.utils import timezone
    
    location = get_object_or_404(WorkLocation, id=location_id)
    
    # Ambil lokasi ini DAN seluruh turunannya (jika ada)
    # Ini penting untuk melihat total karyawan di wilayah tersebut (termasuk sub-wilayah)
    # Gunakan get_descendants(include_self=True) dari MPTT
    sub_locations = location.get_descendants(include_self=True)
    
    # Filter Karyawan: Home Base is within these locations
    employees = Employee.objects.filter(
        home_base__in=sub_locations,
        is_verified=True
    ).select_related('department', 'home_base')
    
    total_employees = employees.count()
    active_employees = employees.filter(is_active=True).count()
    
    # Statistik Kehadiran Hari Ini (Sederhana)
    today = timezone.now().date()
    # Log hari ini untuk karyawan di wilayah ini
    logs_today = AttendanceLog.objects.filter(
        employee__in=employees,
        timestamp__date=today
    ).values('employee').distinct().count()
    
    # Recent Logs for Tab (Last 50)
    recent_logs = AttendanceLog.objects.filter(
        employee__in=employees
    ).select_related('employee', 'captured_at').order_by('-timestamp')[:50]
    
    context = {
        'location': location,
        'employees': employees,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'present_today': logs_today,
        'recent_logs': recent_logs,
    }
    
    return render(request, 'portal/partials/_location_detail.html', context)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from attendance.models import FingerprintDevice, SpreadsheetSource, AttendanceLog, Employee, WorkLocation, EmployeeProfile

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
