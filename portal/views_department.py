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
    List all departments.
    """
    departments = Department.objects.all().order_by('name')
    return render(request, 'portal/department_list.html', {
        'departments': departments,
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
