from app.repositories.db import get_conn, init_db

def column_exists(conn, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)

def run():
    init_db()
    conn = get_conn()
    try:
        if not column_exists(conn, "clients", "conversation_state"):
            conn.execute("ALTER TABLE clients ADD COLUMN conversation_state TEXT NOT NULL DEFAULT 'START';")

        if not column_exists(conn, "clients", "conversation_ctx_json"):
            conn.execute("ALTER TABLE clients ADD COLUMN conversation_ctx_json TEXT NOT NULL DEFAULT '{}';")

        conn.commit()
        print("OK")
    finally:
        conn.close()

if __name__ == "__main__":
    run()
