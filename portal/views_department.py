from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from attendance.models import Department
from .forms import DepartmentForm

def check_hrm_access(user):
    """
    Check if user has access to HRM module (Admin, Superuser, or HRD).
    """
    if user.is_superuser:
        return True
    if hasattr(user, 'employee_profile'):
        return user.employee_profile.role in ['ADMIN', 'HRD']
    return False

@login_required
@user_passes_test(check_hrm_access)
def department_list(request):
    """
    List all departments grouped by location_type for the Explorer View.
    """
    departments = Department.objects.all().order_by('name')
    
    departments_by_type = {
        'HO': [],
        'MILL': [],
        'ESTATE': [],
    }
    
    for dept in departments:
        if dept.location_type in departments_by_type:
            departments_by_type[dept.location_type].append(dept)
            
    return render(request, 'portal/department_list.html', {
        'departments_by_type': departments_by_type,
        'page_title': 'Kelola Departemen'
    })

from django.core.paginator import Paginator
from django.db.models import Q
from attendance.models import Employee, AttendanceLog
from django.utils import timezone

@login_required
@user_passes_test(check_hrm_access)
def department_detail(request, department_id):
    """
    HTMX: Load detail konten untuk panel kanan Department Explorer
    """
    department = get_object_or_404(Department, id=department_id)
    
    # Pagination parameters
    emp_page_size = int(request.GET.get('emp_page_size', 10))
    emp_page = int(request.GET.get('emp_page', 1))
    
    PAGE_SIZE_OPTIONS = [10, 20, 50, 100]
    if emp_page_size not in PAGE_SIZE_OPTIONS:
        emp_page_size = 10
        
    emp_search = request.GET.get('emp_search', '').strip()
    
    # Filter employees
    employees_qs = Employee.objects.filter(
        department=department,
        is_verified=True
    )
    
    if emp_search:
        employees_qs = employees_qs.filter(
            Q(full_name__icontains=emp_search) | 
            Q(nik__icontains=emp_search)
        )
        
    employees_qs = employees_qs.select_related('department', 'home_base').order_by('full_name')
    
    total_employees = employees_qs.count()
    active_employees = employees_qs.filter(is_active=True).count()
    
    # Statistik Hadir Hari Ini
    today = timezone.now().date()
    logs_today = AttendanceLog.objects.filter(
        employee__in=employees_qs,
        timestamp__date=today
    ).values('employee').distinct().count()
    
    emp_paginator = Paginator(employees_qs, emp_page_size)
    employees_page = emp_paginator.get_page(emp_page)
    
    context = {
        'department': department,
        'employees': employees_page,
        'employees_page': employees_page,
        'total_employees': total_employees,
        'active_employees': active_employees,
        'present_today': logs_today,
        'emp_page_size': emp_page_size,
        'page_size_options': PAGE_SIZE_OPTIONS,
        'emp_search': emp_search,
    }
    
    # Validasi HTMX request
    if request.headers.get('HX-Request'):
        return render(request, 'portal/partials/_department_detail.html', context)
        
    # Return HTML fallback if direct link access
    return render(request, 'portal/department_list.html', {
        'department': department,
        'page_title': 'Kelola Departemen'
    })

from django.http import HttpResponse

@login_required
@user_passes_test(check_hrm_access)
def department_add(request):
    """
    HTMX: Add new department.
    """
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Departemen berhasil ditambahkan.')
            # HTMX Redirect to refresh the page
            response = HttpResponse(status=204)
            response['HX-Redirect'] = request.build_absolute_uri(reverse('portal:department_list'))
            return response
    else:
        form = DepartmentForm()
    
    return render(request, 'portal/partials/department_form_modal.html', {
        'form': form,
        'action_url': 'portal:department_add'
    })

@login_required
@user_passes_test(check_hrm_access)
def department_edit(request, department_id):
    """
    HTMX: Edit existing department.
    """
    department = get_object_or_404(Department, id=department_id)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, 'Departemen berhasil diperbarui.')
            response = HttpResponse(status=204)
            response['HX-Redirect'] = request.build_absolute_uri(reverse('portal:department_list'))
            return response
    else:
        form = DepartmentForm(instance=department)
        
    return render(request, 'portal/partials/department_form_modal.html', {
        'form': form,
        'department': department,
        'action_url': 'portal:department_edit',
        'is_edit': True
    })

@login_required
@user_passes_test(check_hrm_access)
def department_delete(request, department_id):
    """
    Delete department.
    """
    department = get_object_or_404(Department, id=department_id)
    
    if request.method == 'POST':
        department.delete()
        messages.success(request, 'Departemen berhasil dihapus.')
        return redirect('portal:department_list')
        
    return redirect('portal:department_list')
