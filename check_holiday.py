import holidays
from datetime import date

id_holidays = holidays.ID(years=[2026])
d = date(2026, 2, 2)
is_holiday = d in id_holidays
print(f"Date: {d}")
print(f"Is Holiday: {is_holiday}")
if is_holiday:
    print(f"Name: {id_holidays.get(d)}")
