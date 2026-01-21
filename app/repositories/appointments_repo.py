from datetime import datetime
from app.repositories.db import get_conn

def list_appointments_for_barber_on_date(barber_id: int, date_iso: str) -> list[dict]:
    """
    date_iso: YYYY-MM-DD
    """
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, start_at, end_at, status
            FROM appointments
            WHERE barber_id = ?
              AND status = 'scheduled'
              AND date(start_at) = date(?)
            ORDER BY start_at
            """,
            (barber_id, date_iso),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_appointment(
    client_id: int,
    barber_id: int,
    service_id: int,
    start_at: str,  # ISO format com timezone: 2026-01-21T14:00:00+03:00
    end_at: str,    # ISO format com timezone
    status: str = "scheduled"
) -> int:
    """
    Cria um agendamento.
    Retorna o appointment.id
    
    Raises:
        ValueError: Se houver conflito de horário ou dados inválidos
    """
    conn = get_conn()
    try:
        # Valida se barber existe e está ativo
        barber = conn.execute(
            "SELECT id FROM barbers WHERE id = ? AND is_active = 1",
            (barber_id,)
        ).fetchone()
        if not barber:
            raise ValueError(f"Barbeiro {barber_id} não encontrado ou inativo")

        # Valida se service existe e está ativo
        service = conn.execute(
            "SELECT id FROM services WHERE id = ? AND is_active = 1",
            (service_id,)
        ).fetchone()
        if not service:
            raise ValueError(f"Serviço {service_id} não encontrado ou inativo")

        # Valida se client existe
        client = conn.execute(
            "SELECT id FROM clients WHERE id = ?",
            (client_id,)
        ).fetchone()
        if not client:
            raise ValueError(f"Cliente {client_id} não encontrado")

        # Valida se horário se sobrepõe com outro agendamento do mesmo barbeiro
        conflict = conn.execute(
            """
            SELECT id FROM appointments
            WHERE barber_id = ?
              AND status = 'scheduled'
              AND start_at < ?
              AND end_at > ?
            """,
            (barber_id, end_at, start_at)
        ).fetchone()
        if conflict:
            raise ValueError(f"Conflito de horário com agendamento {conflict['id']}")

        cur = conn.execute(
            """
            INSERT INTO appointments(client_id, barber_id, service_id, start_at, end_at, status)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (client_id, barber_id, service_id, start_at, end_at, status)
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_appointment_by_id(appointment_id: int) -> dict | None:
    """Retorna um agendamento pelo ID."""
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id, client_id, barber_id, service_id, start_at, end_at, status, created_at, updated_at
            FROM appointments
            WHERE id = ?
            """,
            (appointment_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_appointments_for_client(client_id: int, status: str | None = None) -> list[dict]:
    """Lista agendamentos de um cliente."""
    conn = get_conn()
    try:
        if status:
            rows = conn.execute(
                """
                SELECT id, client_id, barber_id, service_id, start_at, end_at, status, created_at, updated_at
                FROM appointments
                WHERE client_id = ? AND status = ?
                ORDER BY start_at DESC
                """,
                (client_id, status)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, client_id, barber_id, service_id, start_at, end_at, status, created_at, updated_at
                FROM appointments
                WHERE client_id = ?
                ORDER BY start_at DESC
                """,
                (client_id,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cancel_appointment(appointment_id: int) -> None:
    """Cancela um agendamento."""
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE appointments
            SET status = 'cancelled', updated_at = datetime('now')
            WHERE id = ?
            """,
            (appointment_id,)
        )
        conn.commit()
    finally:
        conn.close()
