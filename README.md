<img width="600" height="400" alt="777418587_38218265461119990_1224474160664587274_n" src="https://github.com/user-attachments/assets/4f13037e-6ed5-4bf5-a9a5-5f8680e6aea6" />


# 🌿 Petaling HR - Attendance Core System

Sistem manajemen sumber daya manusia (HRIS) dan absensi berbasis web yang dirancang untuk operasional multi-cabang, perkebunan, dan industri. Sistem ini mengintegrasikan presensi biometrik fisik, pencatatan presensi digital multi-kanal, pengaturan shift kerja dinamis, rekapitulasi, hingga modul asesmen potensi karyawan.

---

## 🚀 Fitur Utama

### 1. Multi-Channel Attendance (Omnichannel Presensi)
* **Integrasi Mesin Biometrik Fisik (ZKTeco)**: Tarik log sidik jari dan wajah secara langsung/otomatis via protokol TCP/IP jaringan lokal menggunakan pustaka `pyzk`.
* **Presensi Lapangan & Mandor**: Dukungan pencatatan absensi mandiri dan pelaporan tim lapangan via integrasi bot pesan instan (Telegram & WhatsApp).
* **Integrasi Google Sheets**: Sinkronisasi data master karyawan dan log absensi dari Google Spreadsheet secara terpusat via API service account.
* **Validasi Dispensasi & Izin**: Sistem penandaan otomatis untuk dispensasi, tugas luar, dinas, sakit, dan izin kerja lengkap dengan catatan alasan (`excuse_reason`).

### 2. Struktur Organisasi & Lokasi Hirarkis (MPTT)
* **Hierarki Wilayah Kerja Fleksibel**: Menggunakan *Modified Preorder Tree Traversal* (`django-mptt`) untuk memetakan struktur kantor pusat, estate, divisi, rayon, hingga afdeling secara bertingkat tanpa batas kedalaman.
* **Validasi Geofencing**: Manajemen titik koordinat GPS (Latitude/Longitude) dan radius toleransi lokasi kerja untuk mencegah kecurangan lokasi.
* **Role-Based Access Control (RBAC)**: Pembagian hak akses granular untuk berbagai peran: `SUPERUSER`, `ADMIN`, `HRD`, `ACCOUNTING`, `KERANI`, `DEPT_ADMIN`, `SUPERVISOR`, dan `PENGUJI`.

### 3. Penjadwalan & Shift Kerja Dinamis
* **Pola Shift Fleksibel**: Pengaturan jadwal kerja reguler, non-shift, dan shift bergilir (Pagi, Siang, Malam) dengan toleransi keterlambatan dan lembur.
* **Bulk Import Roster via Excel**: Unggah jadwal roster kerja bulanan secara massal menggunakan file spreadsheet Excel (`.xlsx`).
* **Kalender Hari Libur Nasional**: Integrasi otomatis dengan kalender hari libur nasional Indonesia (`holidays`) untuk kalkulasi presensi akurat.

### 4. Rekapitulasi & Pelaporan (Payroll-Ready)
* **Rekap Matriks Interaktif**: Tampilan visual matriks absensi harian karyawan selama 1 bulan dengan kode status warna (Hadir, Terlambat, Cuti, Izin, Alpha, Sakit, Libur).
* **Export PDF & Excel**: Cetak laporan rekapitulasi absensi bulanan ke format PDF siap cetak (`xhtml2pdf`/`reportlab`) dan export data analitik ke format spreadsheet (`pandas`/`openpyxl`).
* **Sistem Validasi & Approval**: Alur persetujuan laporan absensi berjenjang (Kerani -> HRD -> Accounting) sebelum data diproses untuk penggajian (*payroll*).

### 5. Talent Management & Psychology Engine
* **Asesmen Kepribadian (DISC / Karakter)**: Modul evaluasi psikotes karyawan dengan pembobotan indikator perilaku positif dan negatif (`PersonalityIndicator`).
* **Kamus Karakter & Sinergi Peran**: Pemetaan kekuatan karakter kerja (`TraitDictionary`) dan evaluasi kecocokan posisi (`RoleSynergyMaster`).
* **ATS-Friendly CV Generator**: Cetak ringkasan profil karyawan, riwayat pekerjaan, dan hasil evaluasi potensi dalam format CV standar *Applicant Tracking System*.

### 6. Audit Trail & Keamanan Tingkat Tinggi
* **Audit History Menyeluruh**: Pencatatan riwayat setiap perubahan data sensitif karyawan menggunakan `django-simple-history`.
* **Logging Akses**: Pelacakan aktivitas sistem (`AccessLog` & `SyncLog`) untuk memudahkan investigasi audit internal.

---

## 🛠️ Tech Stack

### Backend
* **Bahasa**: Python 3.11+
* **Framework**: Django 5.x / 6.x (MTV Architecture)
* **Database**: PostgreSQL 15+ (Didukung oleh `psycopg2-binary`)
* **REST API**: Django REST Framework (DRF) & `djangorestframework-simplejwt`

### Frontend & UI
* **Styling & Komponen**: Bootstrap 5.3, FontAwesome 6, Inter Font
* **Dinamika Halaman**: HTMX (Dynamic partial reload tanpa full page reload), Vanilla JS, SweetAlert2
* **Fitur Antarmuka**: Dark/Light mode toggle, responsive mobile-friendly sidebar, interactive matrix table
---

## ⚙️ Panduan Instalasi & Menjalankan Aplikasi

### Metode 1: Lingkungan Pengembangan Lokal (Windows / Linux)

#### 1. Persyaratan Sistem
* Python 3.11 atau lebih baru
* PostgreSQL Server terpasang dan berjalan di mesin lokal
* Git

#### 2. Clone Repositori & Buat Virtual Environment
```powershell
# Clone repositori
git clone <URL_REPOSITORY_ANDA>
cd attendance_core

# Buat virtual environment
python -m venv venv

# Aktifkan virtual environment
# Di Windows (PowerShell):
.\venv\Scripts\Activate
# Di Linux/macOS:
source venv/bin/activate
```

#### 3. Pasang Dependensi
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Siapkan Database PostgreSQL
Buka terminal PostgreSQL (psql) atau pgAdmin dan jalankan:
```sql
CREATE DATABASE attendance2026;
CREATE USER postgres WITH PASSWORD 'password_anda';
GRANT ALL PRIVILEGES ON DATABASE attendance2026 TO postgres;
```

#### 5. Konfigurasi Variabel Lingkungan (`.env`)
Salin file `.env.example` menjadi `.env` di root proyek:
```powershell
cp .env.example .env
```
Sesuaikan isi file `.env`:
```ini
DB_NAME=attendance2026
DB_USER=postgres
DB_PASSWORD=password_anda
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=kunci_rahasia_acak_yang_aman_dan_panjang
DEBUG=True
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://localhost:8000
```

#### 6. Jalankan Migrasi & Server
```powershell
# Jalankan migrasi database
python manage.py migrate

# Buat akun Superuser (Administrator)
python manage.py createsuperuser

# Jalankan server pengembangan
python manage.py runserver
```
Aplikasi dapat diakses melalui browser di `http://127.0.0.1:8000/`.

---

### Metode 2: Menggunakan Docker Compose (Produksi / Server)

Sistem telah dilengkapi dengan `docker-compose.yml` multi-container (Web, PostgreSQL, Nginx, dan PgAdmin).

```bash
# 1. Pastikan file .env sudah dikonfigurasi dengan SECRET_KEY produksi dan password DB yang kuat
cp .env.example .env

# 2. Build dan jalankan seluruh container di background
docker-compose up -d --build

# 3. Buat superuser di dalam container web
docker-compose exec web python manage.py createsuperuser

# 4. Pantau log sistem
docker-compose logs -f web
```
Aplikasi akan aktif di balik reverse proxy Nginx pada port `80` (atau port yang ditentukan di `nginx.conf`).

---

## 💻 CLI Commands & Sinkronisasi Latar Belakang

Sistem menyediakan beberapa perintah bawaan Django untuk otomasi operasional:

* **Tarik Log Mesin Absensi Biometrik**:
  ```powershell
  python manage.py sync_machine
  ```
* **Sinkronisasi Presensi Harian Lengkap**:
  ```powershell
  python manage.py run_attendance_sync
  ```
* **Import Data Master Karyawan**:
  ```powershell
  python manage.py import_employees
  ```
* **Sinkronisasi Data Mandor / Telegram**:
  ```powershell
  python manage.py sync_mandor_data
  python manage.py sync_telegram_log
  ```

---

## 📄 Lisensi (License)

Proyek ini dilisensikan di bawah **GNU Affero General Public License v3 (AGPL-3.0)**. 
