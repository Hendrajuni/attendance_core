from django.urls import path
from . import views, views_machine, views_department

app_name = 'portal'

urlpatterns = [
    # ... existing patterns ...
    
    # HRM - Department Management
    path('hrm/departments/', views_department.department_list, name='department_list'),
    path('hrm/departments/add/', views_department.department_add, name='department_add'),
    path('hrm/departments/edit/<uuid:department_id>/', views_department.department_edit, name='department_edit'),
    path('hrm/departments/delete/<uuid:department_id>/', views_department.department_delete, name='department_delete'),
    path('hrm/departments/<uuid:department_id>/', views_department.department_detail, name='department_detail'),

    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Machine Management
    path('machines/', views_machine.machine_list, name='machine_list'),
    path('machines/add/', views_machine.machine_add, name='machine_add'),
    path('machines/delete/<uuid:machine_id>/', views_machine.machine_delete, name='machine_delete'),
    path('machines/sync/<uuid:machine_id>/', views_machine.trigger_sync, name='trigger_sync'),
    path('machines/import/', views_machine.machine_import_log, name='machine_import_log'),
    path('machines/toggle/<uuid:machine_id>/', views_machine.machine_toggle_active, name='machine_toggle_active'),
    path('machines/edit/<uuid:machine_id>/', views_machine.machine_edit, name='machine_edit'),

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
    path('notifications/', views.admin_notification_list, name='admin_notification_list'),
    path('notification/<uuid:notification_id>/read/', views.mark_notification_read_htmx, name='mark_notification_read_htmx'),
    
    # Employee Mutation
    path('mutate-employee/<uuid:employee_id>/', views.mutate_employee_view, name='mutate_employee'),
    
    # Employee Detail
    path('employee/<uuid:employee_id>/', views.employee_detail_view, name='employee_detail'),
    
    # Employee Edit
    path('employee/<uuid:employee_id>/edit/', views.employee_edit_view, name='employee_edit'),
    
    # Recap Matrix (Meja Kerja Rekapitulasi)
    path('recap-matrix/', views.recap_matrix_view, name='recap_matrix'),
    path('recap-matrix/export-pdf/', views.export_matrix_pdf, name='export_matrix_pdf'),
    path('roster/import/', views.import_roster_view, name='import_roster'),
    
    # Attendance Cell Edit (HTMX)
    path('attendance/edit/<uuid:employee_id>/<str:date_str>/', views.edit_attendance_modal, name='edit_attendance_modal'),
    path('attendance/save/', views.save_attendance_cell, name='save_attendance_cell'),
    path('attendance/save-roster/', views.save_roster_cell, name='save_roster_cell'),
    
    # WA Cell Edit (HTMX)
    path('wa/edit-cell/<uuid:employee_id>/<str:date_str>/<str:category>/', views.wa_edit_cell, name='wa_edit_cell'),
    path('wa/save-cell/', views.wa_save_cell, name='wa_save_cell'),
    
    # Employee Leave CRUD (HTMX)
    path('leave/add/', views.employee_leave_add, name='employee_leave_add'),
    path('leave/delete/<uuid:leave_id>/', views.employee_leave_delete, name='employee_leave_delete'),
    path('leave/list/<uuid:employee_id>/', views.employee_leave_list, name='employee_leave_list'),
    path('leave/edit/<uuid:leave_id>/', views.employee_leave_edit, name='employee_leave_edit'),
    path('leave/update/<uuid:leave_id>/', views.employee_leave_update, name='employee_leave_update'),

    # FP Cell Edit (HTMX)
    path('fp/edit-cell/<uuid:employee_id>/<str:date_str>/', views.fp_edit_cell, name='fp_edit_cell'),
    path('fp/save-cell/', views.fp_save_cell, name='fp_save_cell'),
    
    # Report Actions
    path('reports/publish/<uuid:report_id>/', views.publish_report, name='publish_report'),
    path('reports/verify/<uuid:report_id>/', views.verify_report, name='verify_report'),
    path('reports/unlock-request/<uuid:report_id>/', views.request_unlock, name='request_unlock'),
    path('reports/unlock-approve/<uuid:report_id>/', views.approve_unlock, name='approve_unlock'),
    path('reports/unlock-reject/<uuid:report_id>/', views.reject_unlock, name='reject_unlock'),
    path('reports/export/<uuid:report_id>/', views.export_matrix_excel, name='export_matrix_excel'),
    path('reports/export-pdf/<uuid:report_id>/', views.export_report_pdf, name='export_report_pdf'),
    path('reports/approve/<uuid:report_id>/', views.approve_payment, name='approve_payment'),
    
    # Dashboard Laporan (Digital Archive)
    path('reports/attendance/', views.attendance_reports_dashboard, name='attendance_reports_dashboard'),
    
    # Personal Print
    path('employee/<uuid:employee_id>/print-modal/', views.print_employee_modal, name='print_employee_modal'),
    path('employee/<uuid:employee_id>/export-pdf/', views.export_employee_pdf, name='export_employee_pdf'),

]
