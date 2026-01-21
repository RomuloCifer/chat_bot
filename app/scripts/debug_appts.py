import sqlite3

DB = "data.sqlite3"
DATE_ISO = "2026-01-20"
BARBER_ID = 1

con = sqlite3.connect(DB)
rows = con.execute(
    """
    SELECT id, barber_id, start_at, end_at, status
    FROM appointments
    WHERE barber_id = ?
      AND date(start_at) = date(?)
    ORDER BY start_at
    """,
    (BARBER_ID, DATE_ISO),
).fetchall()

print(rows)
con.close()
