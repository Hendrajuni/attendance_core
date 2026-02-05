"""
URL Configuration for Attendance App
"""
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # API Endpoints for AJAX
    path('api/sync-machine/<uuid:device_id>/', views.sync_machine_single, name='sync_machine_single'),
    path('api/sync-wa-source/<uuid:source_id>/', views.sync_wa_source_single, name='sync_wa_source_single'),
    path('api/device-status/<uuid:device_id>/', views.device_status_check, name='device_status_check'),
]
