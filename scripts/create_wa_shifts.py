from attendance.models import DailySchedule
from datetime import time

def create_wa_shifts():
    shifts = [
        {
            'name': 'Shift Pagi - WA',
            'code': 'SHIFT-PAGI-WA',
            'clock_in': time(7, 0),
            'clock_out': time(15, 0),
            'enable_checkin_1': True,
            'checkin_1_start': time(9, 0),
            'checkin_1_end': time(10, 0),
            'enable_checkin_2': True,
            'checkin_2_start': time(13, 30),
            'checkin_2_end': time(14, 30),
        },
        {
            'name': 'Shift Sore - WA',
            'code': 'SHIFT-SORE-WA',
            'clock_in': time(15, 0),
            'clock_out': time(23, 0),
            'enable_checkin_1': True,
            'checkin_1_start': time(17, 0),
            'checkin_1_end': time(18, 0),
            'enable_checkin_2': True,
            'checkin_2_start': time(21, 30),
            'checkin_2_end': time(22, 30),
        },
        {
            'name': 'Shift Malam - WA',
            'code': 'SHIFT-MALAM-WA',
            'clock_in': time(23, 0),
            'clock_out': time(7, 0),
            'enable_checkin_1': True,
            'checkin_1_start': time(1, 0),
            'checkin_1_end': time(2, 0),
            'enable_checkin_2': True,
            'checkin_2_start': time(5, 30),
            'checkin_2_end': time(6, 30),
        }
    ]

    for s in shifts:
        obj, created = DailySchedule.objects.get_or_create(
            code=s['code'],
            defaults=s
        )
        if created:
            print(f"[CREATED] {s['name']}")
        else:
            # Update fields just in case they were different (idempotent update)
            updated = False
            for field, value in s.items():
                if getattr(obj, field) != value:
                    setattr(obj, field, value)
                    updated = True
            
            if updated:
                obj.save()
                print(f"[UPDATED] {s['name']}")
            else:
                print(f"[EXISTS] {s['name']}")

if __name__ == "__main__":
    create_wa_shifts()
