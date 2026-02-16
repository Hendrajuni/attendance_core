"""
Dashboard Views for Attendance Monitoring
Provides AJAX endpoints for granular sync operations
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.db import transaction

from .models import FingerprintDevice, SpreadsheetSource, Employee, AttendanceLog, WorkLocation

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD VIEW
# =============================================================================

@staff_member_required
def dashboard(request):
    """
    Main dashboard view showing all devices and sources.
    """
    devices = FingerprintDevice.objects.filter(is_active=True).select_related('location')
    sources = SpreadsheetSource.objects.all().select_related('location')
    locations = WorkLocation.objects.all()
    
    # Get summary stats
    total_employees = Employee.objects.filter(is_verified=True, is_active=True).count()
    pending_employees = Employee.objects.filter(is_verified=False).count()
    today_logs = AttendanceLog.objects.filter(timestamp__date=timezone.now().date()).count()
    
    context = {
        'title': 'Dashboard Operasional',
        'devices': devices,
        'sources': sources,
        'locations': locations,
        'total_employees': total_employees,
        'pending_employees': pending_employees,
        'today_logs': today_logs,
    }
    return render(request, 'admin/attendance_dashboard.html', context)


# =============================================================================
# FINGERPRINT DEVICE SYNC API
# =============================================================================

@staff_member_required
@require_POST
def sync_machine_single(request, device_id):
    """
    Sync a single fingerprint machine by device ID.
    Returns JSON response for AJAX handling.
    """
    try:
        device = FingerprintDevice.objects.get(id=device_id)
    except FingerprintDevice.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'msg': '❌ Device tidak ditemukan'
        }, status=404)
    
    try:
        from zk import ZK
        
        # Connect to device
        zk = ZK(device.ip_address, port=device.port, timeout=10)
        conn = zk.connect()
        
        if not conn:
            return JsonResponse({
                'status': 'error',
                'msg': f'❌ {device.name}: Tidak dapat terhubung'
            })
        
        try:
            # Get attendance logs
            attendances = conn.get_attendance()
            
            if not attendances:
                return JsonResponse({
                    'status': 'success',
                    'msg': f'✅ {device.name}: 0 log baru'
                })
            
            # Process logs
            created_count = 0
            from .utils import determine_category
            
            with transaction.atomic():
                for att in attendances:
                    user_id = att.user_id
                    timestamp = att.timestamp
                    
                    # Make timezone aware
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                    
                    # Find employee (Scoped to Device Location)
                    employee = Employee.objects.filter(
                        device_user_id=user_id,
                        is_active=True,
                        home_base=device.location  # Fix: Prevent cross-location ID conflict
                    ).first()
                    
                    if not employee:
                        continue
                    
                    # Determine category
                    category, _ = determine_category(employee, timestamp)
                    
                    # Create log if not exists
                    log, created = AttendanceLog.objects.get_or_create(
                        employee=employee,
                        timestamp=timestamp,
                        defaults={
                            'status': 'HADIR',
                            'source_type': 'FINGERPRINT',
                            'verification_method': 'FINGERPRINT',
                            'captured_at': device.location,
                            'log_category': category,
                        }
                    )
                    
                    if created:
                        created_count += 1
            
            return JsonResponse({
                'status': 'success',
                'msg': f'✅ {device.name}: {created_count} log baru'
            })
            
        finally:
            conn.disconnect()
            
    except Exception as e:
        logger.exception(f"Error syncing device {device.name}")
        return JsonResponse({
            'status': 'error',
            'msg': f'❌ {device.name}: {str(e)[:50]}'
        })


# =============================================================================
# SPREADSHEET/WA SOURCE SYNC API
# =============================================================================

@staff_member_required
@require_POST  
def sync_wa_source_single(request, source_id):
    """
    Sync a single WA/Telegram spreadsheet source.
    Returns JSON response for AJAX handling.
    """
    try:
        source = SpreadsheetSource.objects.get(id=source_id)
    except SpreadsheetSource.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'msg': '❌ Source tidak ditemukan'
        }, status=404)
    
    try:
        import pandas as pd
        from .utils import determine_category
        
        # Build CSV URL from spreadsheet_id and sheet_name
        csv_url = f"https://docs.google.com/spreadsheets/d/{source.spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={source.sheet_name}"
        
        # Read CSV
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().upper() for c in df.columns]
        
        created_count = 0
        unknown_count = 0
        
        with transaction.atomic():
            for _, row in df.iterrows():
                try:
                    # Parse data
                    tgl_str = str(row.get('TANGGAL', '')).strip()
                    jam_str = str(row.get('JAM ABSEN', '')).strip()
                    user_id = str(row.get('NOMOR WA', '')).strip()
                    nama = row.get('NAMA PEGAWAI', '')
                    coord = str(row.get('KOORDINAT', ''))
                    
                    if not tgl_str or not jam_str:
                        continue
                    
                    # Parse coordinates
                    lat, lng = None, None
                    if ',' in coord:
                        try:
                            lat_part, lng_part = coord.split(',')
                            lat = float(lat_part.strip())
                            lng = float(lng_part.strip())
                        except:
                            pass
                    
                    # Parse timestamp
                    full_ts_str = f"{tgl_str} {jam_str}"
                    timestamp = pd.to_datetime(full_ts_str, dayfirst=True).to_pydatetime()
                    
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                    
                    # Find employee by phone_number
                    employee = Employee.objects.filter(
                        phone_number=user_id,
                        is_active=True
                    ).first()
                    
                    if not employee:
                        # Fallback to telegram_user_id
                        employee = Employee.objects.filter(
                            telegram_user_id=user_id,
                            is_active=True
                        ).first()
                    
                    if not employee:
                        unknown_count += 1
                        continue
                    
                    # Determine category
                    category, _ = determine_category(employee, timestamp)
                    
                    # Create attendance log
                    log, created = AttendanceLog.objects.get_or_create(
                        employee=employee,
                        timestamp=timestamp,
                        defaults={
                            'status': 'HADIR',
                            'source_type': 'TELEGRAM',
                            'verification_method': 'GPS' if lat else 'MANUAL',
                            'captured_at': source.location,
                            'latitude': lat,
                            'longitude': lng,
                            'notes': nama,
                            'log_category': category,
                        }
                    )
                    
                    if created:
                        created_count += 1
                        
                except Exception as e:
                    continue
        
        msg = f'✅ {source.name}: {created_count} log baru'
        if unknown_count > 0:
            msg += f' ({unknown_count} unknown)'
            
        return JsonResponse({
            'status': 'success',
            'msg': msg
        })
        
    except Exception as e:
        logger.exception(f"Error syncing source {source.name}")
        return JsonResponse({
            'status': 'error',
            'msg': f'❌ {source.name}: {str(e)[:50]}'
        })


# =============================================================================
# QUICK STATUS CHECK API
# =============================================================================

@staff_member_required
@require_GET
def device_status_check(request, device_id):
    """
    Quick connectivity check for a fingerprint device.
    """
    try:
        device = FingerprintDevice.objects.get(id=device_id)
    except FingerprintDevice.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': 'Device not found'}, status=404)
    
    try:
        from zk import ZK
        
        zk = ZK(device.ip_address, port=device.port, timeout=5)
        conn = zk.connect()
        
        if conn:
            conn.disconnect()
            return JsonResponse({
                'status': 'online',
                'msg': f'🟢 {device.name}: Online'
            })
        else:
            return JsonResponse({
                'status': 'offline', 
                'msg': f'🔴 {device.name}: Offline'
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'offline',
            'msg': f'🔴 {device.name}: {str(e)[:30]}'
        })
