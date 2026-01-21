from typing import Optional
from app.repositories.db import get_conn
import json
from app.repositories.db import get_conn
def upsert_client_by_key(client_key: str, name: Optional[str] = None) -> int:
    """
    Garante que existe um client com client_key.
    Retorna o client.id
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM clients WHERE client_key = ?",
            (client_key,),
        ).fetchone()

        if row:
            client_id = int(row["id"])
            if name is not None and name.strip():
                conn.execute(
                    "UPDATE clients SET name = ?, updated_at = datetime('now') WHERE id = ?",
                    (name.strip(), client_id),
                )
                conn.commit()
            return client_id

        cur = conn.execute(
            "INSERT INTO clients(client_key, name) VALUES(?, ?)",
            (client_key, name.strip() if name else None),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()
def get_client_state_and_ctx(client_key: str) -> tuple[str, dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT conversation_state, conversation_ctx_json FROM clients WHERE client_key = ?",
            (client_key,),
        ).fetchone()
        if not row:
            return "START", {}
        state = row["conversation_state"] or "START"
        ctx = json.loads(row["conversation_ctx_json"] or "{}")
        return state, ctx
    finally:
        conn.close()

def set_client_state_and_ctx(client_key: str, state: str, ctx: dict) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE clients SET conversation_state = ?, conversation_ctx_json = ?, updated_at = datetime('now') WHERE client_key = ?",
            (state, json.dumps(ctx, ensure_ascii=False), client_key),
        )
        conn.commit()
    finally:
        conn.close()
