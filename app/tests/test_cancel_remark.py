"""
Testes para cancelamento e remarcação de agendamentos.
"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.conversation import handle_message
from app.domain.enums import State
from app.repositories.db import init_db, get_conn


@pytest.fixture(scope="module", autouse=True)
def setup_db_cancel_remark():
    init_db()
    _seed()
    yield


def _seed():
    conn = get_conn()
    try:
        # Limpa
        conn.execute("DELETE FROM appointments")
        conn.execute("DELETE FROM clients")
        conn.execute("DELETE FROM services")
        conn.execute("DELETE FROM barbers")
        # Dados básicos
        conn.execute("INSERT INTO barbers(name, is_active) VALUES(?, 1)", ("João",))  # id 1
        conn.execute("INSERT INTO services(name, duration_minutes, price_cents, is_active) VALUES(?, ?, ?, 1)",
                     ("Corte", 30, 5000))  # id 1
        # Cliente
        conn.execute("INSERT INTO clients(client_key, name) VALUES(?, ?)", ("user_test", "User Test"))  # id 1
        # Um agendamento futuro
        tz = ZoneInfo("America/Sao_Paulo")
        start = (datetime.now(tz) + timedelta(days=2)).replace(hour=15, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)
        conn.execute(
            """
            INSERT INTO appointments(client_id, barber_id, service_id, start_at, end_at, status)
            VALUES(1, 1, 1, ?, ?, 'scheduled')
            """,
            (start.isoformat(), end.isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def test_cancel_flow():
    # Inicia cancelamento
    reply, state, ctx, buttons = handle_message(State.START, {"client_key": "user_test"}, "Cancelar")
    assert state in (State.WAIT_APPOINTMENT_PICK, State.WAIT_CANCEL_CONFIRMATION)

    # Se for seleção direta, pode já estar em confirmação; caso contrário, selecciona o primeiro
    if state == State.WAIT_APPOINTMENT_PICK:
        assert buttons
        first = buttons[0]["id"]
        reply, state, ctx, buttons = handle_message(State.WAIT_APPOINTMENT_PICK, ctx, first)
        assert state == State.WAIT_CANCEL_CONFIRMATION

    # Confirma cancelamento
    reply, state, ctx, buttons = handle_message(State.WAIT_CANCEL_CONFIRMATION, ctx, "Sim")
    assert state == State.START
    assert "cancelado" in reply.lower()


def test_remark_flow():
    # Cria novamente um agendamento futuro para remarcar
    conn = get_conn()
    try:
        tz = ZoneInfo("America/Sao_Paulo")
        start = (datetime.now(tz) + timedelta(days=3)).replace(hour=16, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)
        conn.execute(
            """
            INSERT INTO appointments(client_id, barber_id, service_id, start_at, end_at, status)
            VALUES(1, 1, 1, ?, ?, 'scheduled')
            """,
            (start.isoformat(), end.isoformat())
        )
        conn.commit()
    finally:
        conn.close()

    # Inicia remarcação
    reply, state, ctx, buttons = handle_message(State.START, {"client_key": "user_test"}, "Remarcar")
    # Pode pedir seleção do agendamento se houver mais de um
    if state == State.WAIT_APPOINTMENT_PICK:
        assert buttons
        first = buttons[0]["id"]
        reply, state, ctx, buttons = handle_message(State.WAIT_APPOINTMENT_PICK, ctx, first)
        assert state == State.WAIT_REMARK_DATE
    else:
        assert state == State.WAIT_REMARK_DATE

    # Fornece nova data
    tz = ZoneInfo("America/Sao_Paulo")
    new_date = (datetime.now(tz) + timedelta(days=5)).date()
    reply, state, ctx, buttons = handle_message(State.WAIT_REMARK_DATE, ctx, f"{new_date.day}/{new_date.month}")
    assert state == State.WAIT_REMARK_TIME_PREF

    # Fornece hora e escolhe slot
    reply, state, ctx, buttons = handle_message(State.WAIT_REMARK_TIME_PREF, ctx, "14:00")
    assert state == State.WAIT_REMARK_SLOT_PICK
    first_slot = buttons[0]["label"]
    reply, state, ctx, buttons = handle_message(State.WAIT_REMARK_SLOT_PICK, ctx, first_slot)
    assert state == State.WAIT_REMARK_CONFIRMATION

    # Confirma remarcação
    reply, state, ctx, buttons = handle_message(State.WAIT_REMARK_CONFIRMATION, ctx, "Sim")
    assert state == State.CONFIRMED
    assert "remarcado" in reply.lower()
