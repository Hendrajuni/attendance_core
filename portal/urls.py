from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('tree-explorer/', views.tree_explorer, name='tree_explorer'),
    path('location-detail/<uuid:location_id>/', views.location_detail_view, name='location_detail'),
    
    
    # Sync Log Absensi
    path('sync-logs/', views.sync_logs_view, name='sync_logs'),
    path('sync-logs/machine/<uuid:device_id>/', views.sync_machine_htmx, name='sync_machine_htmx'),
    path('sync-logs/wa/<uuid:source_id>/', views.sync_wa_source_htmx, name='sync_wa_source_htmx'),
    
    # Sync Karyawan Baru
    path('sync-employees/', views.sync_employees_view, name='sync_employees'),
    path('sync-employees/machine/<uuid:device_id>/', views.sync_employee_machine_htmx, name='sync_employee_machine_htmx'),
    path('sync-employees/wa/<uuid:source_id>/', views.sync_employee_wa_htmx, name='sync_employee_wa_htmx'),

    # Ping Machine
    path('ping-machine/<uuid:device_id>/', views.ping_machine_htmx, name='ping_machine_htmx'),

    path('reports/', views.reports, name='reports'),
    path('settings/', views.settings, name='settings'),
    
    # Global Search
    path('search/', views.global_search, name='global_search'),
    
    # Notification Action
    path('notification/<uuid:notification_id>/read/', views.mark_notification_read_htmx, name='mark_notification_read_htmx'),
    
    # Employee Mutation
    path('mutate-employee/<uuid:employee_id>/', views.mutate_employee_view, name='mutate_employee'),
    
    # Employee Detail
    path('employee/<uuid:employee_id>/', views.employee_detail_view, name='employee_detail'),
    
    # Employee Edit
    path('employee/<uuid:employee_id>/edit/', views.employee_edit_view, name='employee_edit'),
    
    # Recap Matrix (Meja Kerja Rekapitulasi)
    path('recap-matrix/', views.recap_matrix_view, name='recap_matrix'),
    
    # Attendance Cell Edit (HTMX)
    path('attendance/edit/<uuid:employee_id>/<str:date_str>/', views.edit_attendance_modal, name='edit_attendance_modal'),
    path('attendance/save/', views.save_attendance_cell, name='save_attendance_cell'),
    
    # WA Cell Edit (HTMX)
    path('wa/edit-cell/<uuid:employee_id>/<str:date_str>/<str:category>/', views.wa_edit_cell, name='wa_edit_cell'),
    path('wa/save-cell/', views.wa_save_cell, name='wa_save_cell'),
    
    # Employee Leave CRUD (HTMX)
    path('leave/add/', views.employee_leave_add, name='employee_leave_add'),
    path('leave/delete/<uuid:leave_id>/', views.employee_leave_delete, name='employee_leave_delete'),
    path('leave/list/<uuid:employee_id>/', views.employee_leave_list, name='employee_leave_list'),
]
