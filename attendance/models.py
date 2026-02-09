import uuid
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey


class WorkLocation(MPTTModel):
    """
    Master lokasi kerja dengan koordinat GPS untuk validasi radius.
    Supports Hierarchy (MPTT).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, help_text="Contoh: Kebun Alpha, Pabrik Kelapa Sawit")
    code = models.CharField(max_length=20, unique=True, help_text="Contoh: KBN-A, PKS, HO")
    
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    
    # GPS Coordinates for radius validation
    latitude = models.FloatField(null=True, blank=True, help_text="Latitude koordinat lokasi")
    longitude = models.FloatField(null=True, blank=True, help_text="Longitude koordinat lokasi")

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        ordering = ['code']
        verbose_name = "Work Location"
        verbose_name_plural = "Work Locations"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Department(models.Model):
    LOCATION_CHOICES = [
        ('HO', 'Head Office (HO)'),
        ('ESTATE', 'Estate / Kebun'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    location_type = models.CharField(max_length=10, choices=LOCATION_CHOICES)

    class Meta:
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return f"{self.name} ({self.get_location_type_display()})"


class FingerprintDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Contoh: Mesin Pos 1")
    ip_address = models.GenericIPAddressField(protocol='IPv4')
    port = models.IntegerField(default=4370)
    location = models.ForeignKey(WorkLocation, on_delete=models.CASCADE, related_name="devices")
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(null=True, blank=True, help_text="Waktu terakhir aktif/ping/sync")

    class Meta:
        ordering = ['name']
        verbose_name = "Fingerprint Device"
        verbose_name_plural = "Fingerprint Devices"

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class SpreadsheetSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, help_text="Contoh: Rekap Absensi Kebun A")
    spreadsheet_id = models.CharField(max_length=150, help_text="ID unik Google Sheet")
    sheet_name = models.CharField(max_length=100, default="Sheet1", help_text="Nama Sheet untuk Log Absensi")
    employee_sheet_name = models.CharField(max_length=100, default="Data-Pegawai", help_text="Nama Sheet untuk Data Pegawai")
    location = models.ForeignKey(WorkLocation, on_delete=models.CASCADE, related_name="spreadsheets")
    last_activity = models.DateTimeField(null=True, blank=True, help_text="Waktu terakhir aktif/pull")

    class Meta:
        ordering = ['name']
        verbose_name = "Spreadsheet Source (Telegram)"
        verbose_name_plural = "Spreadsheet Sources (Telegram)"

    def __str__(self):
        return f"{self.name}"


# =============================================================================
# SCHEDULING MODELS
# =============================================================================

class DailySchedule(models.Model):
    """
    Master jadwal harian yang fleksibel.
    Mendukung 2 gaya: Fingerprint (Legacy) dan Telegram (Multi-Checkpoint).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Nama jadwal. Contoh: Shift Normal, Telegram Kebun")
    code = models.CharField(max_length=20, unique=True, help_text="Kode unik. Contoh: NORMAL, TG-KEBUN")
    
    # --- Basic Hours ---
    clock_in = models.TimeField(help_text="Jam masuk utama")
    clock_out = models.TimeField(help_text="Jam pulang utama")
    break_start = models.TimeField(null=True, blank=True, help_text="Mulai istirahat")
    break_end = models.TimeField(null=True, blank=True, help_text="Selesai istirahat")
    
    # --- Fingerprint Specific (Legacy) ---
    scan_in_start = models.TimeField(null=True, blank=True, help_text="Awal window scan masuk")
    scan_in_end = models.TimeField(null=True, blank=True, help_text="Akhir window scan masuk")
    scan_out_start = models.TimeField(null=True, blank=True, help_text="Awal window scan pulang")
    scan_out_end = models.TimeField(null=True, blank=True, help_text="Akhir window scan pulang")
    late_tolerance = models.IntegerField(default=0, help_text="Toleransi keterlambatan (menit)")
    
    # --- Telegram Specific (Multi-Point) ---
    enable_checkin_1 = models.BooleanField(default=False, help_text="Aktifkan Checkpoint 1")
    checkin_1_start = models.TimeField(null=True, blank=True, help_text="Awal jendela Checkin 1")
    checkin_1_end = models.TimeField(null=True, blank=True, help_text="Akhir jendela Checkin 1")
    
    enable_checkin_2 = models.BooleanField(default=False, help_text="Aktifkan Checkpoint 2")
    checkin_2_start = models.TimeField(null=True, blank=True, help_text="Awal jendela Checkin 2")
    checkin_2_end = models.TimeField(null=True, blank=True, help_text="Akhir jendela Checkin 2")
    
    # --- Telegram GPS ---
    allowed_radius = models.IntegerField(default=1500, help_text="Radius GPS yang diizinkan (meter)")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Daily Schedule"
        verbose_name_plural = "Daily Schedules"

    def __str__(self):
        return f"{self.name} ({self.code})"


class ShiftPattern(models.Model):
    """
    Pola mingguan yang menentukan jadwal untuk setiap hari.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Nama pola shift. Contoh: Shift 5 Hari Kerja")
    code = models.CharField(max_length=20, unique=True)
    
    # 7 Days of the Week
    monday = models.ForeignKey(DailySchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="monday_patterns")
    tuesday = models.ForeignKey(DailySchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="tuesday_patterns")
    wednesday = models.ForeignKey(DailySchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="wednesday_patterns")
    thursday = models.ForeignKey(DailySchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="thursday_patterns")
    friday = models.ForeignKey(DailySchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="friday_patterns")
    saturday = models.ForeignKey(DailySchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="saturday_patterns")
    sunday = models.ForeignKey(DailySchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="sunday_patterns")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Shift Pattern"
        verbose_name_plural = "Shift Patterns"

    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_schedule_for_day(self, weekday):
        """
        Get DailySchedule for a given weekday (0=Monday, 6=Sunday).
        """
        day_map = {
            0: self.monday,
            1: self.tuesday,
            2: self.wednesday,
            3: self.thursday,
            4: self.friday,
            5: self.saturday,
            6: self.sunday,
        }
        return day_map.get(weekday)


class Employee(models.Model):
    """
    Master data karyawan.
    is_verified=False = Data baru (draft/pending review)
    is_verified=True = Data sudah divalidasi (master)
    """
    TYPE_CHOICES = [
        ('HARIAN', 'Buruh Harian'),
        ('STAFF', 'Staff Kantor'),
        ('MANDOR', 'Mandor'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nik = models.CharField(max_length=20, unique=True, verbose_name="NIK")
    full_name = models.CharField(max_length=150)
    employee_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='HARIAN')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    
    # Location Assignment
    home_base = models.ForeignKey(WorkLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name="home_employees", help_text="Lokasi penempatan asli")
    
    # Device & Integration IDs
    device_user_id = models.IntegerField(null=True, blank=True, help_text="ID User di mesin Fingerprint", unique=True)
    telegram_user_id = models.CharField(max_length=50, null=True, blank=True, help_text="ID Telegram untuk Mandor")
    phone_number = models.CharField(max_length=20, null=True, blank=True, help_text="Nomor WA/HP untuk matching log Telegram")
    
    # Verification & Dates
    is_verified = models.BooleanField(default=False, help_text="False = Data baru (butuh review). True = Data master valid.")
    joined_date = models.DateField(null=True, blank=True, help_text="Tanggal mulai bekerja")
    imported_at = models.DateTimeField(null=True, blank=True, help_text="Tanggal data di-import")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = "Karyawan"
        verbose_name_plural = "Karyawan Master"

    def __str__(self):
        return f"{self.full_name} - {self.nik}"


class NewRegistration(Employee):
    """
    Proxy Model untuk menampilkan karyawan baru yang belum diverifikasi.
    Tidak membuat tabel baru di database.
    """
    class Meta:
        proxy = True
        verbose_name = "Pendaftaran Baru"
        verbose_name_plural = "Pendaftaran Baru"


class EmployeeShiftAssignment(models.Model):
    """
    Assignment shift pattern ke karyawan.
    Mendukung effective date untuk perubahan jadwal.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="shift_assignments")
    shift_pattern = models.ForeignKey(ShiftPattern, on_delete=models.CASCADE, related_name="assignments")
    
    effective_from = models.DateField(help_text="Tanggal mulai berlaku")
    effective_to = models.DateField(null=True, blank=True, help_text="Tanggal berakhir (kosong = masih aktif)")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-effective_from']
        verbose_name = "Employee Shift Assignment"
        verbose_name_plural = "Employee Shift Assignments"

    def __str__(self):
        return f"{self.employee.full_name} - {self.shift_pattern.name}"


from django.contrib.auth.models import User

class EmployeeProfile(models.Model):
    """
    Profil tambahan untuk User (RBAC & Lokasi).
    """
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('HRD', 'HRD / Manager'),
        ('ACCOUNTING', 'Accounting'),
        ('KERANI', 'Kerani (Admin Lapangan)'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    assigned_location = models.ForeignKey(WorkLocation, on_delete=models.SET_NULL, null=True, blank=True, help_text="Lokasi kerja utama (untuk filtering data)")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='KERANI')
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class AttendanceLog(models.Model):
    STATUS_CHOICES = [
        ('HADIR', 'Hadir'),
        ('IZIN', 'Izin'),
        ('SAKIT', 'Sakit'),
        ('ALPHA', 'Alpha / Mangkir'),
    ]

    SOURCE_CHOICES = [
        ('FINGERPRINT', 'Fingerprint Machine'),
        ('TELEGRAM', 'Telegram / Spreadsheet'),
    ]

    VERIFICATION_CHOICES = [
        ('FINGER', 'Fingerprint'),
        ('PASSWORD', 'Password'),
        ('FACE', 'Face ID'),
        ('GPS', 'GPS Location'),
        ('MANUAL', 'Manual Input'),
        ('WA', 'WhatsApp / Telegram'),
    ]

    CATEGORY_CHOICES = [
        ('MASUK', 'Masuk'),
        ('CHECKPOINT_1', 'Checkpoint 1'),
        ('ISTIRAHAT', 'Istirahat'),
        ('CHECKPOINT_2', 'Checkpoint 2'),
        ('PULANG', 'Pulang'),
        ('UNKNOWN', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_logs")
    timestamp = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='HADIR')
    
    source_type = models.CharField(max_length=15, choices=SOURCE_CHOICES, default='FINGERPRINT')
    captured_at = models.ForeignKey(WorkLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name="captured_logs", help_text="Lokasi fisik saat data diambil")
    verification_method = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default='FINGER')
    
    log_category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default='UNKNOWN', help_text="Kategori waktu absensi")

    # GPS fields for Telegram
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True, help_text="Alasan izin/sakit atau catatan lain")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Attendance Log"
        verbose_name_plural = "Attendance Logs"
        constraints = [
            models.UniqueConstraint(fields=['employee', 'timestamp'], name='unique_employee_timestamp')
        ]

    def __str__(self):
        loc = self.captured_at.code if self.captured_at else "Unknown"
        return f"{self.employee.full_name} @ {loc} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# =============================================================================
# MUTATION TRACKING MODEL
# =============================================================================

class EmployeeMutation(models.Model):
    """
    Log sejarah mutasi/perpindahan karyawan antar lokasi.
    Preserves historical data integrity.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="mutations")
    old_location = models.ForeignKey(
        WorkLocation, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="mutations_out",
        help_text="Lokasi asal sebelum mutasi"
    )
    new_location = models.ForeignKey(
        WorkLocation, 
        on_delete=models.CASCADE, 
        related_name="mutations_in",
        help_text="Lokasi tujuan setelah mutasi"
    )
    effective_date = models.DateField(help_text="Tanggal efektif mutasi")
    reason = models.TextField(blank=True, null=True, help_text="Alasan mutasi (opsional)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True,
        related_name="processed_mutations",
        help_text="Admin yang memproses mutasi"
    )

    class Meta:
        ordering = ['-effective_date', '-created_at']
        verbose_name = "Employee Mutation"
        verbose_name_plural = "Employee Mutations"

    def __str__(self):
        return f"{self.employee.full_name}: {self.old_location} → {self.new_location} ({self.effective_date})"


# =============================================================================
# PHASE 4: MONTHLY REPORT & VALIDATION SYSTEM
# =============================================================================

class MonthlyReport(models.Model):
    """
    Dokumen Laporan Bulanan per Lokasi.
    Membungkus data absensi untuk validasi berjenjang (Kerani → HRD → Accounting).
    
    Status Workflow:
    DRAFT → SUBMITTED (Kerani lock) → VERIFIED (HRD approve) 
                                    ↳ REJECTED (HRD tolak) → DRAFT
                                    ↳ REQ_REVISI (Kerani minta buka kunci)
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft (Masih bisa diedit)'),
        ('SUBMITTED', 'Dikunci Kerani (Menunggu HRD)'),
        ('VERIFIED', 'Disetujui HRD'),
        ('REQ_REVISI', 'Permintaan Revisi'),
        ('REJECTED', 'Ditolak (Dikembalikan ke Draft)'),
    ]
    
    MONTH_CHOICES = [(i, i) for i in range(1, 13)]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Lokasi & Periode
    location = models.ForeignKey(
        WorkLocation, 
        on_delete=models.CASCADE, 
        related_name="monthly_reports",
        help_text="Lokasi kerja untuk laporan ini"
    )
    period_month = models.IntegerField(
        choices=MONTH_CHOICES,
        help_text="Bulan periode (1-12)"
    )
    period_year = models.IntegerField(
        help_text="Tahun periode (Contoh: 2026)"
    )
    
    # Status & Version Control
    status = models.CharField(
        max_length=15, 
        choices=STATUS_CHOICES, 
        default='DRAFT',
        db_index=True
    )
    version = models.IntegerField(
        default=0, 
        help_text="Versi laporan (bertambah setiap revisi disetujui)"
    )
    
    # Digital Stamps (Audit)
    submitted_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reports_submitted",
        help_text="Kerani yang mengunci laporan"
    )
    submitted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Waktu laporan dikunci oleh Kerani"
    )
    
    verified_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reports_verified",
        help_text="HRD yang memverifikasi laporan"
    )
    verified_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Waktu laporan diverifikasi oleh HRD"
    )
    
    # Notes & Metadata
    notes = models.TextField(
        blank=True, null=True,
        help_text="Catatan revisi/penolakan/keterangan"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_year', '-period_month', 'location__code']
        verbose_name = "Monthly Report"
        verbose_name_plural = "Monthly Reports"
        unique_together = ['location', 'period_month', 'period_year']
        indexes = [
            models.Index(fields=['period_year', 'period_month']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        month_name = [
            '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ][self.period_month]
        return f"{self.location.code} - {month_name} {self.period_year} (v{self.version})"
    
    @property
    def period_display(self):
        """Human-readable period display."""
        month_names = [
            '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ]
        return f"{month_names[self.period_month]} {self.period_year}"
    
    @property
    def is_editable(self):
        """Check if report can be edited (only DRAFT or REJECTED)."""
        return self.status in ('DRAFT', 'REJECTED')
    
    @property
    def is_locked(self):
        """Check if report is locked (SUBMITTED or VERIFIED)."""
        return self.status in ('SUBMITTED', 'VERIFIED')


class ReportHistory(models.Model):
    """
    Audit Log untuk sejarah perubahan status laporan.
    Mencatat siapa yang melakukan aksi dan kapan.
    """
    ACTION_CHOICES = [
        ('CREATE', 'Laporan Dibuat'),
        ('SUBMIT', 'Dikunci/Submit oleh Kerani'),
        ('VERIFY', 'Diverifikasi oleh HRD'),
        ('REJECT', 'Ditolak oleh HRD'),
        ('REQUEST_REVISION', 'Permintaan Revisi'),
        ('REOPEN', 'Dibuka Kembali ke Draft'),
        ('UPDATE', 'Data Diperbarui'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    report = models.ForeignKey(
        MonthlyReport,
        on_delete=models.CASCADE,
        related_name="history"
    )
    actor = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name="report_actions",
        help_text="User yang melakukan aksi"
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        db_index=True
    )
    
    # Previous & New status for complete audit trail
    previous_status = models.CharField(
        max_length=15,
        null=True, blank=True,
        help_text="Status sebelum aksi"
    )
    new_status = models.CharField(
        max_length=15,
        null=True, blank=True,
        help_text="Status setelah aksi"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(
        blank=True, null=True,
        help_text="Alasan/catatan untuk aksi ini"
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Report History"
        verbose_name_plural = "Report Histories"
    
    def __str__(self):
        return f"{self.report} - {self.get_action_display()} ({self.timestamp.strftime('%d/%m/%Y %H:%M')})"


class EmployeeLeave(models.Model):
    """
    Rekaman Izin/Cuti/Sakit Karyawan.
    Mendukung range tanggal untuk cuti beberapa hari.
    """
    LEAVE_TYPES = [
        ('IZIN', 'Izin'),
        ('SAKIT', 'Sakit'),
        ('CUTI', 'Cuti Tahunan'),
        ('CUTI_KHUSUS', 'Cuti Khusus'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField(help_text="Tanggal mulai izin/cuti")
    end_date = models.DateField(help_text="Tanggal selesai izin/cuti")
    notes = models.TextField(blank=True, help_text="Keterangan/alasan")
    
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_leaves',
        help_text="User yang menginput data ini"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = "Employee Leave"
        verbose_name_plural = "Employee Leaves"
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.get_leave_type_display()} ({self.start_date} - {self.end_date})"
    
    @property
    def duration_days(self):
        """Hitung durasi dalam hari"""
        return (self.end_date - self.start_date).days + 1
