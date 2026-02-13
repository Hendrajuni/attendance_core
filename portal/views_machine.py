from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import random

from attendance.models import AttendanceMachine, SyncLog, WorkLocation

@login_required
def machine_list(request):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    role = profile.role if profile else 'UNKNOWN'
    
    # Filter based on role
    if user.is_superuser or role == 'ADMIN':
        machines = AttendanceMachine.objects.all().order_by('name')
    elif role == 'KERANI':
        # Kerani only sees machines in their location
        machines = AttendanceMachine.objects.filter(location=user.employee_profile.assigned_location).order_by('name')
    else:
        # Other roles (e.g. Staff) see nothing or public machines
        machines = AttendanceMachine.objects.none()

    locations = WorkLocation.objects.all()
    
    context = {
        'machines': machines,
        'locations': locations,
        'page_title': 'Manajemen Mesin Absensi',
        'is_admin': user.is_superuser or role == 'ADMIN', # Context for UI logic
    }
    return render(request, 'portal/machine_manager.html', context)

@login_required
@require_http_methods(["POST"])
def machine_add(request):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    role = profile.role if profile else 'UNKNOWN'
    
    if not (user.is_superuser or role == 'ADMIN'):
        return HttpResponseForbidden("Akses Ditolak: Hanya Admin yang dapat menambah mesin.")

    name = request.POST.get('name')
    ip = request.POST.get('ip_address')
    port = request.POST.get('port', 4370)
    location_id = request.POST.get('location_id')
    auto_sync_time = request.POST.get('auto_sync_time')
    
    if name and ip and location_id:
        AttendanceMachine.objects.create(
            name=name,
            ip_address=ip,
            port=port,
            location_id=location_id,
            auto_sync_time=auto_sync_time if auto_sync_time else None
        )
    return redirect('portal:machine_list')

@login_required
@require_http_methods(["DELETE"])
def machine_delete(request, machine_id):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    role = profile.role if profile else 'UNKNOWN'
    
    if not (user.is_superuser or role == 'ADMIN'):
        return HttpResponseForbidden("Akses Ditolak.")

    machine = get_object_or_404(AttendanceMachine, id=machine_id)
    machine.delete()
    return HttpResponse("")

@login_required
@require_http_methods(["POST"])
def trigger_sync(request, machine_id):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    role = profile.role if profile else 'UNKNOWN'
    
    if not (user.is_superuser or role == 'ADMIN'):
        return HttpResponseForbidden("Akses Ditolak: Sinkronisasi jaringan hanya untuk Admin.")

    machine = get_object_or_404(AttendanceMachine, id=machine_id)
    
    # Perform Sync
    machine.perform_sync()
    
    # Return row for HTMX swap
    context = {'machine': machine, 'is_admin': True} # Pass is_admin context
    return render(request, 'portal/partials/_machine_row.html', context)

@login_required
@require_http_methods(["POST"])
def machine_import_log(request):
    """
    Import Limit:
    - Admin: All machines
    - Kerani: Own location machines only
    """
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    role = profile.role if profile else 'UNKNOWN'
    
    machine_id = request.POST.get('machine_id')
    log_file = request.FILES.get('log_file')
    
    if not machine_id or not log_file:
         return redirect('portal:machine_list')

    machine = get_object_or_404(AttendanceMachine, id=machine_id)
    
    # Security Check
    if role == 'KERANI':
        if machine.location != user.employee_profile.assigned_location:
             return HttpResponseForbidden("Akses Ditolak: Anda hanya dapat mengimpor data mesin di lokasi Anda.")
    
    # Process File (Simulation)
    # Read first few lines or count lines
    try:
        # content = log_file.read().decode('utf-8')
        # line_count = len(content.splitlines())
        line_count = random.randint(50, 200) # Mock
        
        SyncLog.objects.create(
            machine=machine,
            status='SUCCESS',
            records_count=line_count,
            log_message=f"Import via Flashdisk: {log_file.name}"
        )
        
        machine.last_sync = timezone.now()
        machine.save()
        
    except Exception as e:
        SyncLog.objects.create(
            machine=machine,
            status='FAILED',
            records_count=0,
            log_message=f"Import Failed: {str(e)}"
        )

    return redirect('portal:machine_list')

@login_required
@require_http_methods(["POST"])
def machine_toggle_active(request, machine_id):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    role = profile.role if profile else 'UNKNOWN'
    
    if not (user.is_superuser or role == 'ADMIN'):
        return HttpResponseForbidden("Akses Ditolak: Hanya Admin yang dapat mengubah status mesin.")

    machine = get_object_or_404(AttendanceMachine, id=machine_id)
    machine.is_active = not machine.is_active
    machine.save()
    
    # Return updated row
    context = {'machine': machine, 'is_admin': True}
    return render(request, 'portal/partials/_machine_row.html', context)

@login_required
def machine_edit(request, machine_id):
    user = request.user
    profile = getattr(user, 'employee_profile', None)
    role = profile.role if profile else 'UNKNOWN'
    
    if not (user.is_superuser or role == 'ADMIN'):
        return HttpResponseForbidden("Akses Ditolak: Hanya Admin yang dapat mengedit mesin.")

    machine = get_object_or_404(AttendanceMachine, id=machine_id)
    locations = WorkLocation.objects.all()

    if request.method == "POST":
        machine.name = request.POST.get('name')
        machine.ip_address = request.POST.get('ip_address')
        machine.port = request.POST.get('port', 4370)
        machine.location_id = request.POST.get('location_id')
        
        auto_sync_time = request.POST.get('auto_sync_time')
        machine.auto_sync_time = auto_sync_time if auto_sync_time else None
        
        machine.save()
        
        # Return updated row
        context = {'machine': machine, 'is_admin': True}
        return render(request, 'portal/partials/_machine_row.html', context)
    
    # GET request: Return form
    context = {
        'machine': machine,
        'locations': locations
    }
    return render(request, 'portal/partials/_machine_edit_form.html', context)
