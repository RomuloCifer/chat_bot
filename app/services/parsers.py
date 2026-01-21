from datetime import date, time
from app.core.timezone import today_br


def parse_br_date(text: str) -> date | None:
    """
    Aceita: DD/MM ou DD/MM/YYYY
    Se vier sem ano, assume ano atual; se já passou, assume próximo ano.
    """
    raw = text.strip()
    if not raw:
        return None

    parts = raw.split("/")
    if len(parts) not in (2, 3):
        return None

    try:
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2]) if len(parts) == 3 else today_br().year
        d = date(year, month, day)

        if len(parts) == 2 and d < today_br():
            d = date(year + 1, month, day)

        return d
    except Exception:
        return None


def parse_br_time(text: str) -> time | None:
    """
    Aceita: "14", "14:00", "14h", "14h30", "14:30"
    """
    raw = text.strip().lower().replace(" ", "")
    if not raw:
        return None

    raw = raw.replace("h", ":")

    if raw.isdigit():
        try:
            h = int(raw)
            if 0 <= h <= 23:
                return time(h, 0)
        except Exception:
            return None

    if raw.endswith(":"):
        raw += "00"

    parts = raw.split(":")
    if len(parts) != 2:
        return None

    try:
        h = int(parts[0])
        m = int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)
    except Exception:
        return None

    return None
