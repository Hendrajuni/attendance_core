# Attendance Core System

Django Setup for Windows Development with Docker Production Target.

## Setup Instructions

### 1. Database Setup (PostgreSQL)
Ensure PostgreSQL is installed and running on your Windows machine (e.g., via pgAdmin or SQL Shell).
Create a database named `attendance_core`.

```sql
CREATE DATABASE attendance_core;
CREATE USER petaling_user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE attendance_core TO petaling_user;
```

### 2. Environment Variables
Copy `.env.example` to `.env` and update the values to match your local PostgreSQL configuration.

```powershell
cp .env.example .env
```

### 3. Installation
Run the following commands in your terminal:

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Running the Project
```powershell
# Migrations
python manage.py migrate

# Run server
python manage.py runserver
```

## 🏗️ Architecture Overview (Auto-Documented by AI)

Sistem ini menggunakan arsitektur monolitik Django yang sangat *data-driven*, terpusat pada aplikasi `attendance` sebagai inti logika bisnis.

### Node Utama (God Nodes)
- **`Employee`**: Pusat dari seluruh sistem yang menjembatani Absensi, Cuti, Shift, Mutasi, dan Laporan.
- **`AttendanceLog`**: Entitas transaksional utama penyimpan log absensi harian (dari mesin, WA, atau manual).
- **`WorkLocation`**: Mengelola titik lokasi kerja dan validasi batas radius GPS.
- **`MonthlyReport`**: Modul agregasi yang membungkus log absensi bulanan untuk keperluan validasi dan *payroll*.

### Modul Kunci
1. **Modul Web Portal (`portal/views.py`)**: Bertindak sebagai UI/UX presentasi. Berisi fungsi seperti Dashboard, Rekap Matriks, dan Export Data. Sangat bergantung pada model di `attendance`.
2. **Modul API (`attendance/api_views.py`)**: Gerbang otentikasi (JWT) dan endpoint sinkronisasi untuk aplikasi *mobile*.
3. **Modul Integrasi Hardware (`AttendanceMachine`)**: Menarik data log secara periodik dari mesin sidik jari/wajah.
4. **Modul Talent & Psikologi**: Menangani penilaian karakter karyawan (`PersonalityTest`, `RoleSynergyMaster`).

*(Catatan: Dokumentasi ini akan diperbarui otomatis oleh AI Assistant setiap kali ada fitur baru atau penyelesaian issue yang signifikan).*
