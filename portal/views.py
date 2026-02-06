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
    Pusat Data Wilayah View
    """
    context = {
        'page_title': 'Pusat Data Wilayah',
    }
    return render(request, 'portal/tree_explorer.html', context)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from attendance.models import FingerprintDevice, SpreadsheetSource, AttendanceLog, Employee, WorkLocation

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
    
    count, error = fetch_users_from_machine(device)
    
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
    
    status_badge = f'<span class="badge bg-success">OK ({count})</span>'
    log_row = f'''
        <tr hx-swap-oob="afterbegin:#sync-log-body">
            <td>{timezone.now().strftime("%H:%M:%S")}</td>
            <td>{device.name}</td>
            <td><span class="badge bg-success">Sukses</span></td>
            <td>Berhasil menarik {count} user baru</td>
        </tr>
    '''
    return HttpResponse(status_badge + log_row)


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
    
    count, error = fetch_users_from_wa_source(source)
    
    if error:
         return HttpResponse(f'''
            <span class="badge bg-danger">Error</span>
             <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{timezone.now().strftime("%H:%M:%S")}</td>
                <td>{source.name}</td>
                <td><span class="badge bg-danger">Gagal</span></td>
                <td class="text-danger">{error}</td>
            </tr>
        ''')

    status_badge = f'<span class="badge bg-success">OK ({count})</span>'
    log_row = f'''
        <tr hx-swap-oob="afterbegin:#sync-log-body">
            <td>{timezone.now().strftime("%H:%M:%S")}</td>
            <td>{source.name}</td>
            <td><span class="badge bg-success">Sukses</span></td>
            <td>Berhasil menarik {count} karyawan baru</td>
        </tr>
    '''
    return HttpResponse(status_badge + log_row)


@login_required
@require_POST
def sync_machine_htmx(request, device_id):
    device = get_object_or_404(FingerprintDevice, id=device_id)
    
    # Simple Access Check
    if hasattr(request.user, 'employee_profile'):
        profile = request.user.employee_profile
        if profile.role == 'KERANI' and profile.assigned_location != device.location:
             return HttpResponse('<span class="badge bg-danger">Akses Ditolak</span>')

    try:
        from zk import ZK
        from attendance.utils import determine_category
        
        zk = ZK(device.ip_address, port=device.port, timeout=10)
        conn = zk.connect()
        
        if not conn:
             return HttpResponse(f'''
                <span class="badge bg-danger">Gagal Koneksi</span>
                <tr hx-swap-oob="afterbegin:#sync-log-body">
                    <td>{timezone.now().strftime("%H:%M:%S")}</td>
                    <td>{device.name}</td>
                    <td><span class="badge bg-danger">Error</span></td>
                    <td class="text-danger">Gagal terhubung ke mesin</td>
                </tr>
            ''')
            
        try:
            attendances = conn.get_attendance()
            created_count = 0
            
            with transaction.atomic():
                for att in attendances:
                    user_id = att.user_id
                    timestamp = att.timestamp
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                        
                    employee = Employee.objects.filter(device_user_id=user_id, is_active=True).first()
                    if not employee: continue
                    
                    category, _ = determine_category(employee, timestamp)
                    _, created = AttendanceLog.objects.get_or_create(
                        employee=employee, timestamp=timestamp,
                        defaults={
                            'status': 'HADIR', 'source_type': 'FINGERPRINT',
                            'verification_method': 'FINGER', 'captured_at': device.location,
                            'log_category': category
                        }
                    )
                    if created: created_count += 1
            
            status_badge = f'<span class="badge bg-success">OK ({created_count})</span>'
            log_row = f'''
                <tr hx-swap-oob="afterbegin:#sync-log-body">
                    <td>{timezone.now().strftime("%H:%M:%S")}</td>
                    <td>{device.name}</td>
                    <td><span class="badge bg-success">Sukses</span></td>
                    <td>Berhasil menarik has {created_count} data baru</td>
                </tr>
            '''
            return HttpResponse(status_badge + log_row)
            
        finally:
            conn.disconnect()

    except Exception as e:
        return HttpResponse(f'''
            <span class="badge bg-danger">Error</span>
            <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{timezone.now().strftime("%H:%M:%S")}</td>
                <td>{device.name}</td>
                <td><span class="badge bg-danger">Exception</span></td>
                <td class="text-danger">{str(e)[:50]}</td>
            </tr>
        ''')

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
        
        created_count = 0
        with transaction.atomic():
            for _, row in df.iterrows():
                tgl_str = str(row.get('TANGGAL', '')).strip()
                jam_str = str(row.get('JAM ABSEN', '')).strip()
                user_id = str(row.get('NOMOR WA', '')).strip()
                
                if not tgl_str or not jam_str: continue
                
                try:
                    full_ts_str = f"{tgl_str} {jam_str}"
                    timestamp = pd.to_datetime(full_ts_str, dayfirst=True).to_pydatetime()
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                        
                    employee = Employee.objects.filter(phone_number=user_id, is_active=True).first()
                    if not employee:
                        employee = Employee.objects.filter(telegram_user_id=user_id, is_active=True).first()
                    if not employee: continue
                    
                    category, _ = determine_category(employee, timestamp)
                    
                    _, created = AttendanceLog.objects.get_or_create(
                         employee=employee, timestamp=timestamp,
                         defaults={
                            'status': 'HADIR', 'source_type': 'SPREADSHEET',
                            'verification_method': 'WA', 'captured_at': source.location,
                            'log_category': category
                        }
                    )
                    if created: created_count += 1
                except: continue

        status_badge = f'<span class="badge bg-success">OK ({created_count})</span>'
        log_row = f'''
            <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{timezone.now().strftime("%H:%M:%S")}</td>
                <td>{source.name}</td>
                <td><span class="badge bg-success">Sukses</span></td>
                <td>Berhasil menarik {created_count} data baru</td>
            </tr>
        '''
        return HttpResponse(status_badge + log_row)

    except Exception as e:
         return HttpResponse(f'''
            <span class="badge bg-danger">Error</span>
             <tr hx-swap-oob="afterbegin:#sync-log-body">
                <td>{timezone.now().strftime("%H:%M:%S")}</td>
                <td>{source.name}</td>
                <td><span class="badge bg-danger">Exception</span></td>
                <td class="text-danger">{str(e)[:50]}</td>
            </tr>
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
