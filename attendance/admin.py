from datetime import date
from django import forms
from django.db import models # Added for global history admin
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils import timezone
from mptt.admin import DraggableMPTTAdmin
from .models import (
    Department, Employee, AttendanceLog, WorkLocation, 
    FingerprintDevice, SpreadsheetSource,
    DailySchedule, ShiftPattern, EmployeeShiftAssignment,
    NewRegistration, EmployeeMutation,  # Proxy Model + Mutation
    MonthlyReport, ReportHistory,  # Phase 4: Report System
    AccessLog, # Audit Log
)
from simple_history.admin import SimpleHistoryAdmin


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


class BulkLocationAssignmentForm(forms.Form):
    """Form for bulk location assignment action."""
    location = forms.ModelChoiceField(
        queryset=WorkLocation.objects.all(),
        label="Pilih Lokasi",
        empty_label="-- Pilih Lokasi --",
        help_text="Pilih lokasi kerja (Home Base) untuk karyawan terpilih"
    )
    
    METHOD_CHOICES = [
        ('FINGERPRINT', 'Mesin Fingerprint'),
        ('WHATSAPP', 'WhatsApp / Telegram'),
        ('MANUAL', 'Manual / Lainnya'),
    ]
    attendance_method = forms.ChoiceField(
        choices=METHOD_CHOICES,
        initial='FINGERPRINT',
        label="Metode Absensi",
        help_text="Tentukan metode absensi utama untuk karyawan ini"
    )


class BulkEmployeeTypeForm(forms.Form):
    """Form for bulk employee type assignment."""
    employee_type = forms.ChoiceField(
        choices=Employee.TYPE_CHOICES,
        label="Pilih Tipe Karyawan",
        help_text="Tentukan tipe karyawan untuk pegawai terpilih"
    )

# =============================================================================
# LOCATION & DEVICE ADMINS
# =============================================================================

@admin.register(WorkLocation)
class WorkLocationAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title', 'code', 'latitude', 'longitude')
    list_display_links = ('indented_title',)
    search_fields = ('name', 'code')
    fieldsets = (
        (None, {
            'fields': ('parent', 'name', 'code')
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
class DailyScheduleAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'code', 'clock_in', 'clock_out', 'enable_checkin_1', 'enable_checkin_2', 'is_active')
    list_filter = ('is_active', 'enable_checkin_1', 'enable_checkin_2')
    search_fields = ('name', 'code')
    
    fieldsets = (
        ('Basic & Fingerprint Configuration', {
            'fields': (
                ('name', 'code'),
                ('clock_in', 'clock_out'),
                ('break_start', 'break_end'),
                ('scan_in_start', 'scan_in_end'),
                ('scan_out_start', 'scan_out_end'),
                ('late_tolerance', 'overtime_tolerance'),
            ),
            'description': 'Konfigurasi jam kerja dasar dan toleransi scan mesin fingerprint.'
        }),
        ('Telegram Configuration (Multi-Checkpoint)', {
            'fields': (
                ('enable_checkin_1', 'checkin_1_start', 'checkin_1_end'),
                ('enable_checkin_2', 'checkin_2_start', 'checkin_2_end'),
                'allowed_radius',
            ),
            'classes': ('collapse',),
            'description': 'Konfigurasi checkpoint tambahan untuk absensi Telegram.'
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )


@admin.register(ShiftPattern)
class ShiftPatternAdmin(SimpleHistoryAdmin):
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
            'description': 'Pilih jadwal harian untuk setiap hari. Kosongkan untuk hari libur.'
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
# EMPLOYEE ADMIN - VERIFIED / MASTER DATA
# =============================================================================

@admin.register(Employee)
class EmployeeAdmin(SimpleHistoryAdmin):
    """
    Admin untuk mengelola Karyawan MASTER (is_verified=True).
    Menampilkan hanya karyawan yang sudah divalidasi.
    """
    list_display = (
        'nik', 'full_name', 'employee_type', 'home_base', 
        'phone_number', 'device_user_id', 'telegram_user_id', 'joined_date', 'is_active'
    )
    list_filter = ('employee_type', 'is_active', 'department', 'home_base', 'joined_date')
    search_fields = ('nik', 'full_name', 'phone_number', 'device_user_id', 'telegram_user_id')
    list_editable = ('is_active',)
    date_hierarchy = 'joined_date'
    actions = ['assign_shift_pattern', 'set_employee_type', 'mark_as_unverified', 'soft_delete_selected']
    
    # Fieldsets for easy mutation (change location/device ID)
    fieldsets = (
        ('Identitas Karyawan', {
            'fields': (
                ('nik', 'full_name'),
                ('employee_type', 'department'),
                ('joined_date', 'is_active'),
            )
        }),
        ('Penempatan & Mutasi', {
            'fields': (
                'home_base',
                ('device_user_id', 'telegram_user_id'),
                'phone_number',
            ),
            'description': 'Edit lokasi dan ID device untuk kasus mutasi/pindah lokasi.'
        }),
        ('Status Verifikasi', {
            'fields': ('is_verified',),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        """Hanya tampilkan karyawan yang sudah VERIFIED."""
        qs = super().get_queryset(request)
        return qs.filter(is_verified=True)
    
    @admin.action(description="📅 Assign Shift Pattern (Bulk)")
    def assign_shift_pattern(self, request, queryset):
        """Bulk action to assign a shift pattern to multiple employees."""
        if request.POST.get('apply'):
            form = BulkShiftAssignmentForm(request.POST)
            if form.is_valid():
                shift_pattern = form.cleaned_data['shift_pattern']
                effective_from = form.cleaned_data['effective_from']
                effective_to = form.cleaned_data['effective_to']
                
                created_count = 0
                updated_count = 0
                
                for employee in queryset:
                    existing = EmployeeShiftAssignment.objects.filter(
                        employee=employee,
                        is_active=True
                    )
                    if existing.exists():
                        existing.update(is_active=False, effective_to=effective_from)
                        updated_count += existing.count()
                    
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
                    f"✅ Berhasil assign shift '{shift_pattern.name}' ke {created_count} karyawan.",
                    messages.SUCCESS
                )
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = BulkShiftAssignmentForm()
        
        context = {
            'title': 'Bulk Assign Shift Pattern',
            'queryset': queryset,
            'form': form,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
            'media': self.media,
        }
        
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
                <li><strong>{{ employee.nik }}</strong> - {{ employee.full_name }}</li>
            {% endfor %}
            </ol>
        </div>
        <form method="post">
            {% csrf_token %}
            <fieldset style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <legend style="font-weight: bold;">Pilih Shift Pattern</legend>
                <table style="margin: 10px 0;">{{ form.as_table }}</table>
            </fieldset>
            {% for obj in queryset %}
                <input type="hidden" name="{{ action_checkbox_name }}" value="{{ obj.pk }}" />
            {% endfor %}
            <div style="margin-top: 20px;">
                <input type="hidden" name="action" value="assign_shift_pattern" />
                <input type="submit" name="apply" value="✅ Confirm Assignment" 
                       style="background: #417690; color: white; padding: 10px 25px; border: none; border-radius: 5px; cursor: pointer;" />
                <a href="{% url 'admin:attendance_employee_changelist' %}" 
                   style="background: #6c757d; color: white; padding: 11px 25px; border-radius: 5px; text-decoration: none; margin-left: 10px;">
                    ❌ Cancel
                </a>
            </div>
        </form>
        {% endblock %}
        """
        
        template = Template(html_template)
        rendered = template.render(RequestContext(request, context))
        return HttpResponse(rendered)

    @admin.action(description="⚡ Generate Employee Type (Bulk Set)")
    def set_employee_type(self, request, queryset):
        """Bulk action to set employee type."""
        if 'apply' in request.POST:
            form = BulkEmployeeTypeForm(request.POST)
            if form.is_valid():
                new_type = form.cleaned_data['employee_type']
                count = queryset.update(employee_type=new_type)
                
                self.message_user(
                    request,
                    f"✅ Berhasil mengubah tipe {count} karyawan menjadi '{new_type}'.",
                    messages.SUCCESS
                )
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = BulkEmployeeTypeForm()
        
        context = {
            'title': 'Generate Employee Type (Bulk Set)',
            'queryset': queryset,
            'form': form,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
            'media': self.media,
        }
        
        from django.template import Template, RequestContext
        from django.http import HttpResponse
        
        html_template = """
        {% extends "admin/base_site.html" %}
        {% load i18n admin_urls %}
        {% block content %}
        <h1>⚡ Generate Employee Type</h1>
        <p>Anda akan mengubah <strong>Tipe Karyawan</strong> untuk <strong>{{ queryset.count }}</strong> data berikut:</p>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; max-height: 200px; overflow-y: auto;">
            <ol>
            {% for employee in queryset %}
                <li><strong>{{ employee.nik }}</strong> - {{ employee.full_name }} (Saat ini: {{ employee.employee_type }})</li>
            {% endfor %}
            </ol>
        </div>
        <form method="post">
            {% csrf_token %}
            <fieldset style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <legend style="font-weight: bold;">Pilih Tipe Baru</legend>
                <table style="margin: 10px 0;">{{ form.as_table }}</table>
            </fieldset>
            {% for obj in queryset %}
                <input type="hidden" name="{{ action_checkbox_name }}" value="{{ obj.pk }}" />
            {% endfor %}
            <div style="margin-top: 20px;">
                <input type="hidden" name="action" value="set_employee_type" />
                <input type="submit" name="apply" value="✅ Update Tipe Karyawan" 
                       style="background: #417690; color: white; padding: 10px 25px; border: none; border-radius: 5px; cursor: pointer;" />
                <a href="#" onclick="window.history.back(); return false;" 
                   style="background: #6c757d; color: white; padding: 11px 25px; border-radius: 5px; text-decoration: none; margin-left: 10px;">
                    ❌ Batal
                </a>
            </div>
        </form>
        {% endblock %}
        """
        
        template = Template(html_template)
        rendered = template.render(RequestContext(request, context))
        return HttpResponse(rendered)
    
    @admin.action(description="⚠️ Kembalikan ke Pendaftaran Baru (Unverify)")
    def mark_as_unverified(self, request, queryset):
        """Move employees back to pending verification."""
        count = queryset.update(is_verified=False)
        self.message_user(
            request,
            f"⚠️ {count} karyawan dikembalikan ke Pendaftaran Baru.",
            messages.WARNING
        )
    
    @admin.action(description="🗑️ Hapus (Soft Delete → Pendaftaran Baru)")
    def soft_delete_selected(self, request, queryset):
        """
        Soft delete: instead of deleting, move back to Pendaftaran Baru.
        This allows admin to permanently delete from there if needed.
        """
        count = queryset.update(is_verified=False, is_active=False)
        self.message_user(
            request,
            f"🗑️ {count} karyawan dipindahkan ke Pendaftaran Baru (non-aktif). "
            f"Hapus permanen dari menu Pendaftaran Baru jika diperlukan.",
            messages.WARNING
        )


# =============================================================================
# NEW REGISTRATION ADMIN - DRAFT / PENDING REVIEW
# =============================================================================

@admin.register(NewRegistration)
class NewRegistrationAdmin(admin.ModelAdmin):
    """
    Admin untuk mengelola Pendaftaran BARU (is_verified=False).
    Data yang di-import dari mesin/telegram masuk ke sini untuk review.
    """
    list_display = (
        'full_name', 'nik', 'home_base', 
        'phone_number', 'device_user_id', 'telegram_user_id', 'imported_at', 'is_active'
    )
    list_filter = ('home_base', 'imported_at', 'is_active')
    search_fields = ('nik', 'full_name', 'phone_number', 'device_user_id', 'telegram_user_id')
    ordering = ['-imported_at', '-created_at']
    actions = ['verify_employees', 'reject_employees', 'assign_location']
    
    fieldsets = (
        ('Identitas (Edit sebelum Approval)', {
            'fields': (
                ('nik', 'full_name'),
                ('employee_type', 'department'),
                'joined_date',
            ),
            'description': 'Perbaiki data sebelum meng-approve ke Master.'
        }),
        ('Penempatan & Device', {
            'fields': (
                'home_base',
                ('device_user_id', 'telegram_user_id'),
            )
        }),
        ('Status', {
            'fields': (('is_verified', 'is_active'),),
        }),
    )
    
    def get_queryset(self, request):
        """Hanya tampilkan karyawan yang BELUM VERIFIED."""
        qs = super().get_queryset(request)
        return qs.filter(is_verified=False)
    
    @admin.action(description="✅ Approve / Verify Selected (Pindahkan ke Master)")
    def verify_employees(self, request, queryset):
        """
        Move selected employees to Master (verified status).
        Auto-generates proper NIK if current NIK starts with TEMP- or TELE-.
        Format: EMP-YYYYMM-XXXX (e.g., EMP-202602-0001)
        """
        now = timezone.now()
        count = 0
        nik_generated = 0
        
        for emp in queryset:
            emp.is_verified = True
            
            # Set joined_date if not set
            if not emp.joined_date:
                emp.joined_date = now.date()
            
            # Auto-generate NIK if temporary (covers TEMP-, TELE-, WA., FG-, T. patterns)
            if emp.nik.startswith(('TEMP-', 'TELE-', 'WA.', 'FG-', 'T.')):
                emp.nik = self._generate_unique_nik(now)
                nik_generated += 1
            
            emp.save()
            count += 1
        
        msg = f"✅ {count} karyawan berhasil di-verify dan dipindahkan ke Karyawan Master."
        if nik_generated > 0:
            msg += f" ({nik_generated} NIK baru di-generate)"
        
        self.message_user(request, msg, messages.SUCCESS)
    
    def _generate_unique_nik(self, now):
        """
        Generate unique NIK in format: PMG-XXXX
        Example: PMG-0001, PMG-0002, ...
        """
        from attendance.models import Employee
        
        prefix = "PMG-"
        
        # Find the highest existing sequence
        existing = Employee.objects.filter(
            nik__startswith=prefix
        ).order_by('-nik').first()
        
        if existing:
            try:
                # Extract the sequence number
                last_seq = int(existing.nik.replace(prefix, ''))
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1
        
        return f"{prefix}{new_seq:04d}"
    
    @admin.action(description="❌ Reject / Hapus Selected")
    def reject_employees(self, request, queryset):
        """Delete rejected registrations."""
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f"❌ {count} pendaftaran dihapus.",
            messages.WARNING
        )

    @admin.action(description="📍 Generate ke Lokasi (Set Location & Verify)")
    def assign_location(self, request, queryset):
        """
        Bulk action to assign location AND verify employees (move to Master).
        This combines setting home_base and running the verification logic.
        """
        if 'apply' in request.POST:
            form = BulkLocationAssignmentForm(request.POST)
            if form.is_valid():
                location = form.cleaned_data['location']
                attendance_method = form.cleaned_data['attendance_method']
                now = timezone.now()
                count = 0
                nik_generated = 0

                for emp in queryset:
                    # 1. Set Location & Method
                    emp.home_base = location
                    emp.attendance_method = attendance_method
                    
                    # 2. Set Verified & Active
                    emp.is_verified = True
                    # Ensure is_active is True if it was False (e.g. from soft delete)
                    emp.is_active = True 
                    
                    # 3. Set Joined Date if empty
                    if not emp.joined_date:
                        emp.joined_date = now.date()
                    
                    # 4. Generate NIK if temporary (covers TEMP-, TELE-, WA., FG-, T. patterns)
                    if emp.nik.startswith(('TEMP-', 'TELE-', 'WA.', 'FG-', 'T.')):
                        emp.nik = self._generate_unique_nik(now)
                        nik_generated += 1
                    
                    emp.save()
                    count += 1
                
                msg = f"✅ Berhasil set lokasi '{location.name}' dan memindahkan {count} karyawan ke Master."
                if nik_generated > 0:
                    msg += f" ({nik_generated} NIK baru di-generate)"

                self.message_user(request, msg, messages.SUCCESS)
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = BulkLocationAssignmentForm()
            
        context = {
            'title': 'Generate ke Lokasi (Bulk Assign)',
            'queryset': queryset,
            'form': form,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
            'media': self.media,
        }
        
        from django.template import Template, RequestContext
        from django.http import HttpResponse
        
        html_template = """
        {% extends "admin/base_site.html" %}
        {% load i18n admin_urls %}
        {% block content %}
        <h1>📍 Generate ke Lokasi (Bulk Assign)</h1>
        <p>Anda akan mengubah lokasi (Home Base) untuk <strong>{{ queryset.count }}</strong> karyawan berikut:</p>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; max-height: 200px; overflow-y: auto;">
            <ol>
            {% for employee in queryset %}
                <li><strong>{{ employee.nik }}</strong> - {{ employee.full_name }}</li>
            {% endfor %}
            </ol>
        </div>
        <form method="post">
            {% csrf_token %}
            <fieldset style="padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <legend style="font-weight: bold;">Pilih Lokasi Baru</legend>
                <table style="margin: 10px 0;">{{ form.as_table }}</table>
            </fieldset>
            {% for obj in queryset %}
                <input type="hidden" name="{{ action_checkbox_name }}" value="{{ obj.pk }}" />
            {% endfor %}
            <div style="margin-top: 20px;">
                <input type="hidden" name="action" value="assign_location" />
                <input type="submit" name="apply" value="✅ Simpan Lokasi" 
                       style="background: #417690; color: white; padding: 10px 25px; border: none; border-radius: 5px; cursor: pointer;" />
                <a href="#" onclick="window.history.back(); return false;" 
                   style="background: #6c757d; color: white; padding: 11px 25px; border-radius: 5px; text-decoration: none; margin-left: 10px;">
                    ❌ Batal
                </a>
            </div>
        </form>
        {% endblock %}
        """
        
        template = Template(html_template)
        rendered = template.render(RequestContext(request, context))
        return HttpResponse(rendered)


# =============================================================================
# USER ADMIN CUSTOMIZATION (RBAC)
# =============================================================================

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import EmployeeProfile

class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = 'Employee Profile (RBAC & Location)'
    fk_name = 'user'

# Unregister default User admin
admin.site.unregister(User)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (EmployeeProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'get_location', 'is_staff')
    
    def get_role(self, obj):
        try:
            return obj.employee_profile.get_role_display()
        except EmployeeProfile.DoesNotExist:
            return "-"
    get_role.short_description = 'Role'
    
    def get_location(self, obj):
        try:
            return obj.employee_profile.assigned_location.code
        except (EmployeeProfile.DoesNotExist, AttributeError):
            return "-"
    get_location.short_description = 'Assigned Location'


# =============================================================================
# ATTENDANCE LOG ADMIN
# =============================================================================

@admin.register(AttendanceLog)
class AttendanceLogAdmin(SimpleHistoryAdmin):
    list_display = ('timestamp', 'employee', 'status', 'log_category', 'source_type', 'captured_at', 'verification_method')
    list_filter = ('status', 'log_category', 'source_type', 'timestamp', 'captured_at', 'employee__department')
    search_fields = ('employee__full_name', 'employee__nik')
    date_hierarchy = 'timestamp'


# =============================================================================
# EMPLOYEE MUTATION ADMIN (AUDIT LOG)
# =============================================================================

@admin.register(EmployeeMutation)
class EmployeeMutationAdmin(admin.ModelAdmin):
    """
    Admin untuk melihat riwayat mutasi karyawan.
    Readonly untuk menjaga integritas data historis.
    """
    list_display = ('employee', 'old_location', 'new_location', 'effective_date', 'created_by', 'created_at')
    list_filter = ('effective_date', 'new_location', 'old_location', 'created_at')
    search_fields = ('employee__full_name', 'employee__nik', 'reason')
    date_hierarchy = 'effective_date'
    
    # Make all fields readonly to preserve audit trail
    readonly_fields = ('employee', 'old_location', 'new_location', 'effective_date', 'reason', 'created_at', 'created_by')
    
    # Disable add/change/delete permissions (log only via frontend)
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete (emergency)


# =============================================================================
# PHASE 4: MONTHLY REPORT & VALIDATION ADMIN
# =============================================================================

class ReportHistoryInline(admin.TabularInline):
    """Inline display of report history for audit trail."""
    model = ReportHistory
    extra = 0
    readonly_fields = ('timestamp', 'actor', 'action', 'previous_status', 'new_status', 'comment')
    can_delete = False
    ordering = ['-timestamp']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    """
    Admin untuk mengelola Laporan Bulanan.
    Menampilkan status, versi, dan stempel digital untuk tracking workflow.
    """
    list_display = (
        'location', 'period_display', 'status', 'version',
        'submitted_by', 'submitted_at', 'verified_by', 'verified_at'
    )
    list_filter = ('status', 'period_year', 'period_month', 'location')
    search_fields = ('location__name', 'location__code', 'notes')
    date_hierarchy = 'created_at'
    ordering = ['-period_year', '-period_month', 'location__code']
    
    readonly_fields = (
        'submitted_by', 'submitted_at', 'verified_by', 'verified_at',
        'created_at', 'updated_at', 'version'
    )
    
    inlines = [ReportHistoryInline]
    
    fieldsets = (
        ('Identitas Laporan', {
            'fields': (
                'location',
                ('period_month', 'period_year'),
                ('status', 'version'),
            )
        }),
        ('Stempel Digital (Audit Trail)', {
            'fields': (
                ('submitted_by', 'submitted_at'),
                ('verified_by', 'verified_at'),
            ),
            'classes': ('collapse',),
            'description': 'Informasi stempel digital untuk validasi berjenjang.'
        }),
        ('Catatan & Metadata', {
            'fields': (
                'notes',
                ('created_at', 'updated_at'),
            ),
            'classes': ('collapse',),
        }),
    )
    
    def period_display(self, obj):
        """Display period as readable string."""
        return obj.period_display
    period_display.short_description = 'Periode'
    period_display.admin_order_field = 'period_month'


@admin.register(ReportHistory)
class ReportHistoryAdmin(admin.ModelAdmin):
    """
    Admin untuk melihat riwayat perubahan status laporan.
    Readonly untuk menjaga integritas audit trail.
    """
    list_display = ('report', 'action', 'actor', 'previous_status', 'new_status', 'timestamp')
    list_filter = ('action', 'timestamp', 'report__location')
    search_fields = ('report__location__name', 'report__location__code', 'comment', 'actor__username')
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    readonly_fields = ('report', 'actor', 'action', 'previous_status', 'new_status', 'timestamp', 'comment')
    
    # Disable add/change/delete permissions (log only via system)
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete (emergency)


# =============================================================================
# AUDIT LOG ADMIN (ACCESS LOG)
# =============================================================================

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'status', 'ip_address', 'user_agent_short')
    list_filter = ('action', 'status', 'timestamp', 'user__employee_profile__role')
    search_fields = ('user__username', 'ip_address', 'user_agent')
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    def user_agent_short(self, obj):
        return (obj.user_agent[:50] + '...') if obj.user_agent and len(obj.user_agent) > 50 else obj.user_agent
    user_agent_short.short_description = "User Agent"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# =============================================================================
# DATA CHANGE LOG ADMIN (GLOBAL HISTORY)
# =============================================================================

class ReadOnlyHistoryAdmin(admin.ModelAdmin):
    """
    Base Admin class for Historical Models to make them read-only and searchable.
    """
    list_display = ('history_date', 'history_user', 'history_type', 'history_id')
    list_filter = ('history_date', 'history_type', 'history_user')
    ordering = ['-history_date']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

# Register Historical Models
# Note: We must unregister them first if they are already registered (unlikely but safe)
# The model names usually default to "Historical [model name]"

def register_historical_model(model, title):
    try:
        history_model = model.history.model
    except AttributeError:
        # Model might not have history enabled
        return
    
    if admin.site.is_registered(history_model):
        admin.site.unregister(history_model)

    @admin.register(history_model)
    class HistoryAdmin(ReadOnlyHistoryAdmin):
        # Dynamically set list_display based on fields, excluding internal ones
        list_display = ['history_date', 'history_user', 'history_type'] + \
                       [f.name for f in history_model._meta.fields 
                        if f.name not in ['history_id', 'history_date', 'history_user', 'history_type', 'history_change_reason', 'history_relation_id']][:5]
        
        search_fields = [f.name for f in history_model._meta.fields 
                         if isinstance(f, (models.CharField, models.TextField))][:3]
        
        verbose_name_plural = title

# Register specific historical models
# Check if models are imported. If not, they should be imported at top of file. 
# Assuming they are already imported as per file content view.

register_historical_model(Employee, "Riwayat Karyawan (Global)")
register_historical_model(AttendanceLog, "Riwayat Absensi (Global)")
register_historical_model(DailySchedule, "Riwayat Jadwal (Global)")
register_historical_model(ShiftPattern, "Riwayat Shift (Global)")
