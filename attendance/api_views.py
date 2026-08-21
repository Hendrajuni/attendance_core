from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import IntegrityError
from .models import Employee
from .serializers import DailyContextSerializer, AttendanceLogSerializer


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class MobileTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        if 'username' in attrs:
            attrs['username'] = attrs['username'].upper()
        
        data = super().validate(attrs)
        # Aplikasi Android mengekspektasikan balasan JSON {"token": "eyJhb..."}
        return {"token": data["access"]}

class MobileTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/token/
    Endpoint kustom untuk Login (JWT) yang mengembalikan format JSON {"token": "access_token"}
    sesuai ekspektasi aplikasi Android.
    """
    serializer_class = MobileTokenObtainPairSerializer


class MobileContextAPIView(APIView):
    """
    GET /api/mobile/context/
    Mengembalikan data DailyContext (Briefing Pagi) untuk aplikasi Android.
    Mencakup data lokasi, radius geofence, serta daftar tombol absensi yang valid untuk hari ini.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Kita mengasumsikan username dari auth.User dikonfigurasi sama dengan NIK pada Employee
            employee = Employee.objects.get(nik=request.user.username)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Data profil karyawan (Master) tidak ditemukan. Pastikan Username login sama dengan NIK."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DailyContextSerializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobileSyncAPIView(APIView):
    """
    POST /api/mobile/sync/
    Menerima payload JSON (Array) berisi log absensi dari antrean (queue) aplikasi offline-first.
    Melakukan proses validasi, deteksi duplikasi, dan pencatatan anomali (Polisi Pencatat).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            employee = Employee.objects.get(nik=request.user.username)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Data profil karyawan (Master) tidak ditemukan."},
                status=status.HTTP_404_NOT_FOUND
            )

        payload = request.data
        if not isinstance(payload, list):
            return Response(
                {"error": "Payload harus berupa list/array dari objek absensi."},
                status=status.HTTP_400_BAD_REQUEST
            )

        success_count = 0
        duplicate_count = 0
        error_count = 0

        for index, item in enumerate(payload):
            serializer = AttendanceLogSerializer(data=item)
            if serializer.is_valid():
                log_category = serializer.validated_data.get('log_category')
                is_mock = item.get('is_mock_location', False)
                
                # Polisi Pencatat (Anomaly Detection)
                # Menyisipkan flag anomali ke kolom 'notes' agar dapat dibaca HRD
                if log_category == 'GPS_OFF' or is_mock:
                    existing_notes = serializer.validated_data.get('notes', '') or ''
                    anomaly_tags = []
                    if log_category == 'GPS_OFF':
                        anomaly_tags.append("[GPS_DIMATIKAN_SAAT_ABSEN]")
                    if is_mock:
                        anomaly_tags.append("[MOCK_LOCATION/FAKE_GPS_TERDETEKSI]")
                    
                    serializer.validated_data['notes'] = " ".join(anomaly_tags) + " " + existing_notes

                try:
                    # Menambahkan objek employee ke method create melalui serializer.save()
                    serializer.save(employee=employee)
                    success_count += 1
                except IntegrityError:
                    # Mengabaikan data ganda yang disebabkan oleh retries dari mobile app
                    duplicate_count += 1
                except Exception as e:
                    error_count += 1
            else:
                error_count += 1

        # Harapan Balasan: {"message": "Sync berhasil"} sesuai dokumentasi
        return Response({"message": "Sync berhasil"}, status=status.HTTP_200_OK)
