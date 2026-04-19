"""
URL Configuration for Attendance App
"""
from django.urls import path
from . import views
from . import talent_views

app_name = 'attendance'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # API Endpoints for AJAX
    path('api/sync-machine/<uuid:device_id>/', views.sync_machine_single, name='sync_machine_single'),
    path('api/sync-wa-source/<uuid:source_id>/', views.sync_wa_source_single, name='sync_wa_source_single'),
    path('api/device-status/<uuid:device_id>/', views.device_status_check, name='device_status_check'),

    # Talent Development & HR Assessment
    path('talent/', talent_views.talent_dashboard, name='talent_dashboard'),
    path('talent/manual-input/', talent_views.talent_manual_form, name='talent_manual_form'),
    path('talent/print/', talent_views.talent_print_report, name='talent_print_report'),
    path('talent/<uuid:pk>/', talent_views.talent_detail, name='talent_detail'),
    
    # HTMX Endpoints for Talent Dashboard
    path('talent/location/<uuid:location_id>/', talent_views.talent_location_dashboard_htmx, name='talent_location_dashboard_htmx'),
    path('talent/global-dashboard/', talent_views.talent_location_dashboard_htmx, name='talent_location_global_htmx'),
]
