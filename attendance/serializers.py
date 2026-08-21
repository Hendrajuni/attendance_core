from rest_framework import serializers
from django.utils import timezone
from .models import AttendanceLog, Employee

class AttendanceLogSerializer(serializers.ModelSerializer):
    """
    Serializer untuk menerima payload absensi (Clock-In/Out) dari aplikasi Android secara offline-first.
    Menerima koordinat dan kategori presensi, lalu menetapkan atribut otomatis untuk rekaman dari mobile app.
    """
    # Memastikan field wajib ada dalam payload
    timestamp = serializers.DateTimeField(required=True)
    latitude = serializers.FloatField(required=True)
    longitude = serializers.FloatField(required=True)
    log_category = serializers.CharField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = AttendanceLog
        fields = ['timestamp', 'latitude', 'longitude', 'log_category', 'notes']

    def validate(self, attrs):
        # Kita bisa menambahkan custom validation tambahan di sini
        # Contoh: Memastikan kategori log ada dalam kategori yang didukung
        valid_categories = ['MASUK', 'CHECKPOINT_1', 'ISTIRAHAT', 'CHECKPOINT_2', 'PULANG']
        if attrs.get('log_category') not in valid_categories:
            raise serializers.ValidationError({"log_category": "Kategori log absensi tidak valid."})
        return attrs

    def create(self, validated_data):
        # Catatan: `employee` biasanya di-pass dari context request (misal lewat request.user.employee_profile)
        # pada layer view. Disini kita berasumsi `employee` dikirim lewat serializer.save(employee=obj)
        
        # Hardcode metadata untuk submission dari Mobile App
        validated_data['source_type'] = 'FINGERPRINT'
        validated_data['verification_method'] = 'GPS'
        
        # Simpan ke tabel AttendanceLog
        return super().create(validated_data)


class DailyContextSerializer(serializers.Serializer):
    """
    Serializer untuk 'Briefing Pagi' ke Android App.
    Merangkum informasi geofencing dan daftar absensi yang valid (Shift) untuk hari ini.
    """
    employee_id = serializers.UUIDField(source='id', read_only=True)
    name = serializers.CharField(source='full_name', read_only=True)
    geofence = serializers.SerializerMethodField()
    valid_buttons = serializers.SerializerMethodField()

    def _get_today_schedule(self, obj):
        """Helper untuk mendapatkan jadwal harian dari Shift Pattern karyawan."""
        today = timezone.localtime(timezone.now()).date()
        weekday = today.weekday() # 0 = Monday, 6 = Sunday

        # Mengambil shift yang aktif pada hari ini
        assignment = obj.shift_assignments.filter(
            effective_from__lte=today,
            is_active=True
        ).order_by('-effective_from').first()

        if not assignment:
            return None
        
        return assignment.shift_pattern.get_schedule_for_day(weekday)

    def get_geofence(self, obj):
        """Mengekstrak koordinat GPS lokasi utama karyawan beserta radius toleransi jadwal."""
        location = obj.home_base
        schedule = self._get_today_schedule(obj)
        
        lat = location.latitude if location else None
        lng = location.longitude if location else None
        radius = schedule.allowed_radius if schedule else 1500 # Default 1500 meter jika jadwal tidak ada
        
        return {
            "latitude": lat,
            "longitude": lng,
            "allowed_radius": radius
        }

    def get_valid_buttons(self, obj):
        """Menghasilkan array button absensi (CLOCK_IN, CLOCK_OUT, dsb) beserta rentang validasinya."""
        schedule = self._get_today_schedule(obj)
        buttons = []
        
        if not schedule:
            return buttons

        # Tombol Absen MASUK
        if schedule.scan_in_start and schedule.scan_in_end:
            buttons.append({
                "category": "CLOCK_IN",
                "start": schedule.scan_in_start.strftime("%H:%M"),
                "end": schedule.scan_in_end.strftime("%H:%M")
            })
            
        # Tombol CHECKPOINT 1
        if schedule.enable_checkin_1 and schedule.checkin_1_start and schedule.checkin_1_end:
            buttons.append({
                "category": "CHECKPOINT_1",
                "start": schedule.checkin_1_start.strftime("%H:%M"),
                "end": schedule.checkin_1_end.strftime("%H:%M")
            })

        # Tombol ISTIRAHAT
        if schedule.break_start and schedule.break_end:
            buttons.append({
                "category": "ISTIRAHAT",
                "start": schedule.break_start.strftime("%H:%M"),
                "end": schedule.break_end.strftime("%H:%M")
            })

        # Tombol CHECKPOINT 2
        if schedule.enable_checkin_2 and schedule.checkin_2_start and schedule.checkin_2_end:
            buttons.append({
                "category": "CHECKPOINT_2",
                "start": schedule.checkin_2_start.strftime("%H:%M"),
                "end": schedule.checkin_2_end.strftime("%H:%M")
            })

        # Tombol Absen PULANG
        if schedule.scan_out_start and schedule.scan_out_end:
            buttons.append({
                "category": "CLOCK_OUT",
                "start": schedule.scan_out_start.strftime("%H:%M"),
                "end": schedule.scan_out_end.strftime("%H:%M")
            })

        return buttons

    def to_representation(self, instance):
        data = super().to_representation(instance)
        schedule = self._get_today_schedule(instance)
        if schedule:
            data['shift'] = schedule.name
            data['shift_in'] = schedule.clock_in.strftime("%H:%M") if schedule.clock_in else "08:00"
            data['shift_out'] = schedule.clock_out.strftime("%H:%M") if schedule.clock_out else "16:00"
        else:
            data['shift'] = "Tidak Ada Jadwal"
            data['shift_in'] = "08:00"
            data['shift_out'] = "16:00"
            
        from django.utils import timezone
        from .models import AttendanceLog
        today = timezone.localtime(timezone.now()).date()
        logs = AttendanceLog.objects.filter(employee=instance, timestamp__date=today).order_by('timestamp')
        
        data['today_clock_in'] = None
        data['today_clock_out'] = None
        data['today_cp1'] = None
        data['today_istirahat'] = None
        data['today_cp2'] = None

        for log in logs:
            time_str = timezone.localtime(log.timestamp).strftime("%H:%M")
            if log.log_category == 'MASUK' and not data['today_clock_in']:
                data['today_clock_in'] = time_str
            elif log.log_category == 'PULANG' and not data['today_clock_out']:
                data['today_clock_out'] = time_str
            elif log.log_category == 'CHECKPOINT_1' and not data['today_cp1']:
                data['today_cp1'] = time_str
            elif log.log_category == 'ISTIRAHAT' and not data['today_istirahat']:
                data['today_istirahat'] = time_str
            elif log.log_category == 'CHECKPOINT_2' and not data['today_cp2']:
                data['today_cp2'] = time_str
                
        # Fallback to keep backward compatibility with existing Dashboard logic
        if not data['today_clock_in'] and logs.exists():
            data['today_clock_in'] = timezone.localtime(logs.first().timestamp).strftime("%H:%M")
        if not data['today_clock_out'] and logs.count() > 1:
            data['today_clock_out'] = timezone.localtime(logs.last().timestamp).strftime("%H:%M")
            
        return data


