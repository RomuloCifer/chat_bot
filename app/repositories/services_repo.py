from app.repositories.db import get_conn

def list_active_services() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, duration_minutes, price_cents FROM services WHERE is_active = 1 ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def find_service_by_name(name: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, name, duration_minutes, price_cents FROM services WHERE is_active = 1 AND name = ?",
            (name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
