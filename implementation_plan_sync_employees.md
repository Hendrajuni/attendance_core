# Additional Employee Sync Features

## User Goal
The user wants to be able to "Pull Employee Data" from both:
1.  **Google Spreadsheets** (already handled by `sync_mandor_data` but needs UI button)
2.  **Fingerprint Devices** (needs new logic to pull user data from machine)

## Implementation Plan

### 1. Backend: Employee Sync from Fingerprint (`sync_machine_users`)
Create a new management command and API endpoint to pull user data (Name, ID) from ZK machines.
- **Command**: `sync_machine_users`
- **Logic**: Use `zk.get_users()` to retrieve user list.
- **Action**: Create/Update `Employee` records based on `device_user_id`. Default to 'HARIAN' type and 'UNVERIFIED' status.

### 2. Backend: API Endpoints
Update `views.py` to add:
- `sync_machine_users_single(request, device_id)`: Ajax endpoint for fingerprint user sync.
- `sync_spreadsheet_employees_single(request, source_id)`: Ajax endpoint that wraps existing `sync_mandor_data` logic.

### 3. Frontend: Dashboard Update
Update `attendance_dashboard.html`:
- Add a new column or button group for "Employee Data".
- **Fingerprint Table**: Add "busts_in_silhouette Sync Users" button next to "Sync Logs".
- **Spreadsheet Table**: Add "busts_in_silhouette Sync Employees" button next to "Pull Data".

### 4. Admin Integration (Optional but requested)
The user showed Admin Change Forms. We can add a custom `change_form_template` for `FingerprintDevice` and `SpreadsheetSource` that includes these buttons, but adding them to the Dashboard is higher impact and cleaner. I will focus on the Dashboard first as the primary control center.

## Technical Details

### Fingerprint User Sync
```python
users = conn.get_users()
for user in users:
    # user.uid, user.name, user.user_id (this is the one we map to device_user_id), user.privilege, user.password, user.group_id, user.card
    # Create/Update Employee
```

### Spreadsheet User Sync
Reuse logic from `sync_mandor_data` but refactored into a reusable function or utility so it can be called from both Command and View.
