from datetime import date
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

        if len(parts) == 2:
            if d < today_br():
                d = date(year + 1, month, day)

        return d
    except Exception:
        return None
