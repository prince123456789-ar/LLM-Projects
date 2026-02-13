from datetime import timedelta


def suggest_next_slots(start_hour: int = 9, count: int = 3, slot_minutes: int = 30):
    # Returns suggested slots from current UTC hour forward.
    from datetime import datetime, timezone

    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if base.hour < start_hour:
        base = base.replace(hour=start_hour)

    slots = []
    cursor = base + timedelta(hours=1)
    for _ in range(count):
        end = cursor + timedelta(minutes=slot_minutes)
        slots.append((cursor, end))
        cursor = end + timedelta(minutes=15)

    return slots
