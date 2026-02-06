from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('tree-explorer/', views.tree_explorer, name='tree_explorer'),
    
    # Sync Log Absensi
    path('sync-logs/', views.sync_logs_view, name='sync_logs'),
    path('sync-logs/machine/<uuid:device_id>/', views.sync_machine_htmx, name='sync_machine_htmx'),
    path('sync-logs/wa/<uuid:source_id>/', views.sync_wa_source_htmx, name='sync_wa_source_htmx'),
    
    # Sync Karyawan Baru
    path('sync-employees/', views.sync_employees_view, name='sync_employees'),
    path('sync-employees/machine/<uuid:device_id>/', views.sync_employee_machine_htmx, name='sync_employee_machine_htmx'),
    path('sync-employees/wa/<uuid:source_id>/', views.sync_employee_wa_htmx, name='sync_employee_wa_htmx'),

    path('sync-employees/wa/<uuid:source_id>/', views.sync_employee_wa_htmx, name='sync_employee_wa_htmx'),

    path('reports/', views.reports, name='reports'),
    path('settings/', views.settings, name='settings'),
    
    # Global Search
    path('search/', views.global_search, name='global_search'),
]
