"""
Testes para scheduler de reminders.
"""
import pytest
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from app.jobs.reminders_24h import (
    list_appointments_for_reminder,
    mark_reminder_sent,
    format_reminder_message,
)
from app.repositories.db import init_db, get_conn


@pytest.fixture(scope="module", autouse=True)
def setup_db_scheduler():
    init_db()
    _seed()
    yield


def _seed():
    """Semeia dados de teste: agendamentos para amanhã (com e sem reminder)."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM appointments")
        conn.execute("DELETE FROM clients")
        conn.execute("DELETE FROM services")
        conn.execute("DELETE FROM barbers")
        
        # Dados básicos
        conn.execute("INSERT INTO barbers(name, is_active) VALUES(?, 1)", ("João",))
        conn.execute("INSERT INTO services(name, duration_minutes, price_cents, is_active) VALUES(?, ?, ?, 1)",
                     ("Corte", 30, 5000))
        conn.execute("INSERT INTO clients(client_key, name) VALUES(?, ?)", ("user_test", "Test User"))
        
        # Agendamentos: um para amanhã SEM reminder, outro para amanhã COM reminder
        tz = ZoneInfo("America/Sao_Paulo")
        tomorrow = (datetime.now(tz) + timedelta(days=1)).date()
        
        # Sem reminder (alvo do teste)
        start1 = datetime.combine(tomorrow, time(14, 0), tzinfo=tz)
        end1 = start1 + timedelta(minutes=30)
        conn.execute(
            """
            INSERT INTO appointments(client_id, barber_id, service_id, start_at, end_at, status, reminder_sent_at)
            VALUES(1, 1, 1, ?, ?, 'scheduled', NULL)
            """,
            (start1.isoformat(), end1.isoformat())
        )
        
        # Com reminder (não deve aparecer na lista)
        start2 = datetime.combine(tomorrow, time(15, 0), tzinfo=tz)
        end2 = start2 + timedelta(minutes=30)
        conn.execute(
            """
            INSERT INTO appointments(client_id, barber_id, service_id, start_at, end_at, status, reminder_sent_at)
            VALUES(1, 1, 1, ?, ?, 'scheduled', datetime('now'))
            """,
            (start2.isoformat(), end2.isoformat())
        )
        
        conn.commit()
    finally:
        conn.close()


def test_list_appointments_for_reminder():
    """Testa se lista apenas agendamentos sem reminder."""
    tz = ZoneInfo("America/Sao_Paulo")
    appts = list_appointments_for_reminder(tz)
    
    # Deve retornar 1 (sem reminder)
    assert len(appts) == 1
    assert appts[0]["reminder_sent_at"] is None
    assert appts[0]["status"] == "scheduled"


def test_mark_reminder_sent():
    """Testa marcação de reminder enviado."""
    tz = ZoneInfo("America/Sao_Paulo")
    
    # Antes de marcar, lista 1 agendamento
    appts = list_appointments_for_reminder(tz)
    assert len(appts) == 1
    appt_id = appts[0]["id"]
    
    # Marca como enviado
    mark_reminder_sent(appt_id)
    
    # Depois, lista deve estar vazia
    appts = list_appointments_for_reminder(tz)
    assert len(appts) == 0


def test_format_reminder_message():
    """Testa formatação da mensagem de lembrete."""
    tz = ZoneInfo("America/Sao_Paulo")
    tomorrow = (datetime.now(tz) + timedelta(days=1)).date()
    
    appt = {
        "id": 1,
        "barber_id": 1,
        "service_id": 1,
        "start_at": datetime.combine(tomorrow, time(14, 0), tzinfo=tz).isoformat(),
    }
    
    msg = format_reminder_message(appt, tz)
    
    # Verificações básicas
    assert "🔔" in msg
    assert "lembrete" in msg.lower() or "agendamento" in msg.lower()
    assert "João" in msg or "Corte" in msg  # Nome do barbeiro ou serviço
