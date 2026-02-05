from datetime import date
from django import forms
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from .models import (
    Department, Employee, AttendanceLog, WorkLocation, 
    FingerprintDevice, SpreadsheetSource,
    DailySchedule, ShiftPattern, EmployeeShiftAssignment
)


# =============================================================================
# BULK ASSIGNMENT FORM
# =============================================================================

class BulkShiftAssignmentForm(forms.Form):
    """Form for bulk shift assignment action."""
    shift_pattern = forms.ModelChoiceField(
        queryset=ShiftPattern.objects.filter(is_active=True),
        label="Shift Pattern",
        help_text="Pilih pola shift yang akan di-assign ke karyawan terpilih"
    )
    effective_from = forms.DateField(
        initial=date.today,
        label="Tanggal Mulai Berlaku",
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Tanggal mulai assignment ini berlaku"
    )
    effective_to = forms.DateField(
        required=False,
        label="Tanggal Berakhir (Opsional)",
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Kosongkan jika assignment berlaku tanpa batas waktu"
    )


# =============================================================================
# LOCATION & DEVICE ADMINS
# =============================================================================

@admin.register(WorkLocation)
class WorkLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'latitude', 'longitude')
    search_fields = ('name', 'code')
    fieldsets = (
        (None, {
            'fields': ('name', 'code')
        }),
        ('GPS Coordinates', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',),
            'description': 'Koordinat GPS untuk validasi radius absensi Telegram'
        }),
    )


@admin.register(FingerprintDevice)
class FingerprintDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip_address', 'port', 'location', 'is_active')
    list_filter = ('location', 'is_active')
    search_fields = ('name', 'ip_address')


@admin.register(SpreadsheetSource)
class SpreadsheetSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'spreadsheet_id', 'sheet_name', 'location')
    list_filter = ('location',)
    search_fields = ('name', 'spreadsheet_id')


# =============================================================================
# SCHEDULING ADMINS
# =============================================================================

@admin.register(DailySchedule)
class DailyScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'clock_in', 'clock_out', 'enable_checkin_1', 'enable_checkin_2', 'is_active')
    list_filter = ('is_active', 'enable_checkin_1', 'enable_checkin_2')
    search_fields = ('name', 'code')
    
    fieldsets = (
        # Section 1: Basic & Fingerprint Configuration
        ('Basic & Fingerprint Configuration', {
            'fields': (
                ('name', 'code'),
                ('clock_in', 'clock_out'),
                ('break_start', 'break_end'),
                ('scan_in_start', 'scan_in_end'),
                ('scan_out_start', 'scan_out_end'),
                'late_tolerance',
            ),
            'description': 'Konfigurasi jam kerja dasar dan toleransi scan mesin fingerprint.'
        }),
        # Section 2: Telegram Configuration
        ('Telegram Configuration (Multi-Checkpoint)', {
            'fields': (
                ('enable_checkin_1', 'checkin_1_start', 'checkin_1_end'),
                ('enable_checkin_2', 'checkin_2_start', 'checkin_2_end'),
                'allowed_radius',
            ),
            'classes': ('collapse',),
            'description': 'Konfigurasi checkpoint tambahan untuk absensi Telegram. Aktifkan checkbox untuk menggunakan fitur ini.'
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )


@admin.register(ShiftPattern)
class ShiftPatternAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active')
        }),
        ('Weekly Schedule', {
            'fields': (
                'monday', 'tuesday', 'wednesday', 'thursday', 
                'friday', 'saturday', 'sunday'
            ),
            'description': 'Pilih jadwal harian untuk setiap hari dalam seminggu. Kosongkan untuk hari libur.'
        }),
    )


@admin.register(EmployeeShiftAssignment)
class EmployeeShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'shift_pattern', 'effective_from', 'effective_to', 'is_active')
    list_filter = ('is_active', 'shift_pattern', 'effective_from')
    search_fields = ('employee__full_name', 'employee__nik')
    autocomplete_fields = ['employee', 'shift_pattern']
    date_hierarchy = 'effective_from'


# =============================================================================
# DEPARTMENT ADMIN
# =============================================================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'location_type')
    list_filter = ('location_type',)
    search_fields = ('name',)


# =============================================================================
# EMPLOYEE ADMIN (with Bulk Assignment Action)
# =============================================================================

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('nik', 'full_name', 'employee_type', 'department', 'home_base', 'is_active', 'device_user_id', 'telegram_user_id')
    list_filter = ('employee_type', 'is_active', 'department', 'home_base')
    search_fields = ('nik', 'full_name', 'device_user_id', 'telegram_user_id')
    list_editable = ('is_active',)
    actions = ['assign_shift_pattern']
    
    @admin.action(description="📅 Assign Shift Pattern (Bulk)")
    def assign_shift_pattern(self, request, queryset):
        """
        Bulk action to assign a shift pattern to multiple employees.
        Shows an intermediate page with a form to select the shift pattern.
        """
        # If POST and form data exists, process the assignment
        if request.POST.get('apply'):
            form = BulkShiftAssignmentForm(request.POST)
            if form.is_valid():
                shift_pattern = form.cleaned_data['shift_pattern']
                effective_from = form.cleaned_data['effective_from']
                effective_to = form.cleaned_data['effective_to']
                
                created_count = 0
                updated_count = 0
                
                for employee in queryset:
                    # Deactivate existing active assignments for this employee
                    existing = EmployeeShiftAssignment.objects.filter(
                        employee=employee,
                        is_active=True
                    )
                    if existing.exists():
                        existing.update(is_active=False, effective_to=effective_from)
                        updated_count += existing.count()
                    
                    # Create new assignment
                    EmployeeShiftAssignment.objects.create(
                        employee=employee,
                        shift_pattern=shift_pattern,
                        effective_from=effective_from,
                        effective_to=effective_to,
                        is_active=True
                    )
                    created_count += 1
                
                self.message_user(
                    request,
                    f"✅ Berhasil assign shift '{shift_pattern.name}' ke {created_count} karyawan. "
                    f"({updated_count} assignment lama di-nonaktifkan)",
                    messages.SUCCESS
                )
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = BulkShiftAssignmentForm()
        
        # Render intermediate page with inline template
        context = {
            'title': 'Bulk Assign Shift Pattern',
            'queryset': queryset,
            'form': form,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
            'media': self.media,
        }
        
        # Using inline HTML template - render directly with Template class
        from django.template import Template, RequestContext
        from django.http import HttpResponse
        
        html_template = """
        {% extends "admin/base_site.html" %}
        {% load i18n admin_urls %}

        {% block content %}
        <h1>📅 Bulk Assign Shift Pattern</h1>
        <p>Anda akan mengassign shift pattern ke <strong>{{ queryset.count }}</strong> karyawan berikut:</p>
        
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; max-height: 200px; overflow-y: auto;">
            <ol>
            {% for employee in queryset %}
                <li><strong>{{ employee.nik }}</strong> - {{ employee.full_name }} 
                    <small style="color: #666;">({{ employee.get_employee_type_display }})</small>
                </li>
            {% endfor %}
            </ol>
        </div>
        
        <form method="post">
            {% csrf_token %}
            
            <fieldset style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <legend style="font-weight: bold; padding: 0 10px;">Pilih Shift Pattern</legend>
                
                <table style="margin: 10px 0;">
                    {{ form.as_table }}
                </table>
            </fieldset>

            {% for obj in queryset %}
                <input type="hidden" name="{{ action_checkbox_name }}" value="{{ obj.pk }}" />
            {% endfor %}
            
            <div style="margin-top: 20px;">
                <input type="hidden" name="action" value="assign_shift_pattern" />
                <input type="submit" name="apply" value="✅ Confirm Assignment" 
                       style="background: #417690; color: white; padding: 10px 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;" />
                <a href="{% url 'admin:attendance_employee_changelist' %}" 
                   style="background: #6c757d; color: white; padding: 11px 25px; border-radius: 5px; text-decoration: none; margin-left: 10px; font-size: 14px;">
                    ❌ Cancel
                </a>
            </div>
        </form>
        {% endblock %}
        """
        
        template = Template(html_template)
        rendered = template.render(RequestContext(request, context))
        return HttpResponse(rendered)


# =============================================================================
# ATTENDANCE LOG ADMIN
# =============================================================================

@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'employee', 'status', 'log_category', 'source_type', 'captured_at', 'verification_method')
    list_filter = ('status', 'log_category', 'source_type', 'timestamp', 'captured_at', 'employee__department')
    search_fields = ('employee__full_name', 'employee__nik')
    date_hierarchy = 'timestamp'


