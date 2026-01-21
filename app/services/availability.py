from datetime import datetime, timedelta, time
from app.core.config import (
    BUSINESS_START, BUSINESS_END,
    LUNCH_START, LUNCH_END,
    SLOT_STEP_MINUTES,
)
from app.repositories.appointments_repo import list_appointments_for_barber_on_date

def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))

def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end

def generate_suggestions(
    date_iso: str,
    barber_id: int,
    duration_minutes: int,
    preferred_time: time,
    tz,
    max_suggestions: int = 3,
) -> list[datetime]:
    day = datetime.fromisoformat(date_iso).date()

    business_start_dt = datetime.combine(day, _t(BUSINESS_START), tzinfo=tz)
    business_end_dt = datetime.combine(day, _t(BUSINESS_END), tzinfo=tz)

    lunch_start_dt = datetime.combine(day, _t(LUNCH_START), tzinfo=tz)
    lunch_end_dt = datetime.combine(day, _t(LUNCH_END), tzinfo=tz)

    appts = list_appointments_for_barber_on_date(barber_id, date_iso)
    busy = []
    for a in appts:
        busy.append((
            datetime.fromisoformat(a["start_at"]).replace(tzinfo=tz),
            datetime.fromisoformat(a["end_at"]).replace(tzinfo=tz),
        ))

    step = timedelta(minutes=SLOT_STEP_MINUTES)
    dur = timedelta(minutes=duration_minutes)

    pref_dt = datetime.combine(day, preferred_time, tzinfo=tz)

    def is_valid(start: datetime) -> bool:
        end = start + dur

        if start < business_start_dt or end > business_end_dt:
            return False

        if overlaps(start, end, lunch_start_dt, lunch_end_dt):
            return False

        for b_start, b_end in busy:
            if overlaps(start, end, b_start, b_end):
                return False

        return True

    suggestions: list[datetime] = []
    seen: set[str] = set()

    def add(dt: datetime):
        key = dt.strftime("%H:%M")
        if key in seen:
            return
        if is_valid(dt):
            suggestions.append(dt)
            seen.add(key)

    # tenta exatamente na ordem:
    # 0, -30, -60, +30, +60, -90, +90, ...
    add(pref_dt)

    k = 1
    while len(suggestions) < max_suggestions:
        minus_dt = pref_dt - (step * k)
        plus_dt = pref_dt + (step * k)

        add(minus_dt)
        if len(suggestions) >= max_suggestions:
            break

        add(plus_dt)

        if minus_dt < business_start_dt and (plus_dt + dur) > business_end_dt:
            break

        k += 1

    return suggestions[:max_suggestions]
