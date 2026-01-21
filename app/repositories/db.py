import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data.sqlite3"

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db() -> None:
    schema_sql = """
    CREATE TABLE IF NOT EXISTS barbers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS services (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      duration_minutes INTEGER NOT NULL,
      price_cents INTEGER NULL,
      is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS clients (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      client_key TEXT NOT NULL UNIQUE, -- no web chat: client_id; no WhatsApp: phone
      name TEXT NULL,
      total_cuts INTEGER NOT NULL DEFAULT 0,
      total_cancels INTEGER NOT NULL DEFAULT 0,
      last_appointment_at TEXT NULL,
      conversation_state TEXT NOT NULL DEFAULT 'START',
      conversation_ctx_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS appointments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      client_id INTEGER NOT NULL,
      barber_id INTEGER NOT NULL,
      service_id INTEGER NOT NULL,
      start_at TEXT NOT NULL,
      end_at TEXT NOT NULL,
      status TEXT NOT NULL, -- scheduled, cancelled
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      FOREIGN KEY (client_id) REFERENCES clients(id),
      FOREIGN KEY (barber_id) REFERENCES barbers(id),
      FOREIGN KEY (service_id) REFERENCES services(id)
    );

    CREATE INDEX IF NOT EXISTS idx_appointments_barber_start ON appointments(barber_id, start_at);
    CREATE INDEX IF NOT EXISTS idx_appointments_client_status ON appointments(client_id, status);
    """
    conn = get_conn()
    try:
      conn.executescript(schema_sql)
      conn.commit()
    finally:
      conn.close()
