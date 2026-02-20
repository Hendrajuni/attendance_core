
filename = r"d:\dev\attendance_core\portal\views.py"
with open(filename, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if "def edit_attendance_modal" in line:
            print(f"Found at line {i}: {line.strip()}")
