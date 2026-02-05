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
