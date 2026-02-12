from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import AttendanceLog, MonthlyReport
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=AttendanceLog)
def update_monthly_report_last_edit(sender, instance, created, **kwargs):
    """
    Otomatis update 'last_modified_by' dan 'updated_at' di MonthlyReport
    setiap kali ada perubahan data absensi (AttendanceLog).
    """
    try:
        # Tentukan Lokasi Laporan
        # Prioritas: captured_at > employee.home_base
        location = instance.captured_at
        if not location and instance.employee:
            location = instance.employee.home_base
            
        if not location:
            return  # Tidak bisa menentukan lokasi, skip
            
        # Tentukan Periode
        # Gunakan local time untuk akurasi periode
        local_dt = timezone.localtime(instance.timestamp)
        month = local_dt.month
        year = local_dt.year
        
        # Cari MonthlyReport yang sesuai
        report = MonthlyReport.objects.filter(
            location=location,
            period_month=month,
            period_year=year
        ).first()
        
        if report:
            # Update Timestamp
            # Logika "Last Edit": Setiap kali ada perubahan di log, report dianggap berubah.
            # Field updated_at akan otomatis berubah karena auto_now=True,
            # tapi kita paksa save() untuk memicu update tersebut jika tidak ada field lain yang berubah.
            
            # Note: last_modified_by idealnya diisi oleh user yang login. 
            # Karena signal tidak punya context request, kita biarkan field ini 
            # di-handle oleh View yang melakukan save() jika memungkinkan.
            # Signal ini menjadi safety net untuk setidaknya mengupdate waktu 'updated_at'.

            report.updated_at = timezone.now()
            report.save(update_fields=['updated_at'])
            
            logger.info(f"Signal: Updated MonthlyReport {report} timestamp due to log change.")
            
    except Exception as e:
        logger.error(f"Error updating MonthlyReport from signal: {e}")
