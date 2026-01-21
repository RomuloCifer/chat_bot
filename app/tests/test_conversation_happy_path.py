"""
Testes do fluxo de agendamento (happy path).

Cenário: Cliente agendando um horário do início ao fim.
"""
import pytest
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from app.services.conversation import handle_message
from app.domain.models import ConversationContext
from app.domain.enums import State
from app.repositories.db import init_db, get_conn
from app.repositories.barbers_repo import list_active_barbers
from app.repositories.services_repo import list_active_services


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Inicializa BD para testes."""
    init_db()
    _seed_test_data()
    yield


def _seed_test_data():
    """Popula BD com dados de teste."""
    conn = get_conn()
    try:
        # Limpa dados anteriores
        conn.execute("DELETE FROM appointments")
        conn.execute("DELETE FROM clients")
        conn.execute("DELETE FROM services")
        conn.execute("DELETE FROM barbers")
        
        # Insere barbeiros
        conn.execute("INSERT INTO barbers(name, is_active) VALUES(?, 1)", ("João",))
        conn.execute("INSERT INTO barbers(name, is_active) VALUES(?, 1)", ("Carlos",))
        
        # Insere serviços
        conn.execute("INSERT INTO services(name, duration_minutes, price_cents, is_active) VALUES(?, ?, ?, 1)",
                    ("Corte", 30, 5000))
        conn.execute("INSERT INTO services(name, duration_minutes, price_cents, is_active) VALUES(?, ?, ?, 1)",
                    ("Barba", 20, 3000))
        
        conn.commit()
    finally:
        conn.close()


def test_greeting():
    """Testa saudação inicial."""
    reply, state, ctx, buttons = handle_message(State.START, {}, "Olá!")
    
    assert "Bem-vindo" in reply or "barbearia" in reply.lower()
    assert state == State.START
    assert len(buttons) == 0


def test_booking_flow_complete():
    """
    Testa o fluxo completo de agendamento.
    
    Steps:
    1. Usuário diz que quer agendar
    2. Escolhe um barbeiro
    3. Escolhe um serviço
    4. Define a data
    5. Define uma hora
    6. Escolhe um slot
    7. Confirma
    """
    ctx = {}
    
    # Step 1: Intent de booking
    reply, state, ctx, buttons = handle_message(State.START, ctx, "Quero agendar um horário")
    assert state == State.WAIT_BARBER
    assert len(buttons) >= 2  # Pelo menos João e Carlos
    
    # Step 2: Escolhe um barbeiro
    reply, state, ctx, buttons = handle_message(State.WAIT_BARBER, ctx, "João")
    assert state == State.WAIT_SERVICE
    assert len(buttons) >= 2  # Pelo menos Corte e Barba
    
    # Step 3: Escolhe um serviço
    reply, state, ctx, buttons = handle_message(State.WAIT_SERVICE, ctx, "Corte")
    assert state == State.WAIT_DATE
    
    # Step 4: Define a data (próximo dia útil)
    tomorrow = (datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(days=1)).date()
    date_str = f"{tomorrow.day}/{tomorrow.month}"
    
    reply, state, ctx, buttons = handle_message(State.WAIT_DATE, ctx, date_str)
    assert state == State.WAIT_TIME_PREF
    
    # Step 5: Define uma hora
    reply, state, ctx, buttons = handle_message(State.WAIT_TIME_PREF, ctx, "14:00")
    assert state == State.WAIT_SLOT_PICK
    assert len(buttons) >= 1  # Pelo menos uma sugestão de horário
    
    # Step 6: Escolhe um slot (primeira sugestão)
    first_slot = buttons[0]["label"]
    reply, state, ctx, buttons = handle_message(State.WAIT_SLOT_PICK, ctx, first_slot)
    assert state == State.WAIT_CONFIRMATION
    assert "confirma" in reply.lower() or "confirmar" in reply.lower()
    
    # Step 7: Confirma
    reply, state, ctx, buttons = handle_message(State.WAIT_CONFIRMATION, ctx, "Sim")
    assert state == State.CONFIRMED
    assert "✅" in reply or "confirmado" in reply.lower()


def test_cancel_from_wait_barber():
    """Testa cancelamento durante escolha de barbeiro."""
    reply, state, ctx, _ = handle_message(State.START, {}, "Agendar")
    assert state == State.WAIT_BARBER
    
    # Cancela
    reply, state, ctx, _ = handle_message(State.WAIT_BARBER, ctx, "Cancelar")
    assert state == State.START


def test_cancel_from_wait_confirmation():
    """Testa mudança de barbeiro na confirmação."""
    ctx = {}
    
    # Fluxo normal até confirmação
    _, state, ctx, _ = handle_message(State.START, ctx, "Agendar")
    _, state, ctx, _ = handle_message(State.WAIT_BARBER, ctx, "João")
    _, state, ctx, _ = handle_message(State.WAIT_SERVICE, ctx, "Corte")
    tomorrow = (datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(days=1)).date()
    _, state, ctx, _ = handle_message(State.WAIT_DATE, ctx, f"{tomorrow.day}/{tomorrow.month}")
    _, state, ctx, _ = handle_message(State.WAIT_TIME_PREF, ctx, "14:00")
    _, state, ctx, buttons = handle_message(State.WAIT_SLOT_PICK, ctx, buttons[0]["label"])
    assert state == State.WAIT_CONFIRMATION
    
    # Não confirma
    reply, state, ctx, _ = handle_message(State.WAIT_CONFIRMATION, ctx, "Não")
    assert state == State.WAIT_BARBER


def test_invalid_date():
    """Testa validação de data inválida."""
    ctx = {}
    
    # Chega até WAIT_DATE
    _, state, ctx, _ = handle_message(State.START, ctx, "Agendar")
    _, state, ctx, _ = handle_message(State.WAIT_BARBER, ctx, "João")
    _, state, ctx, _ = handle_message(State.WAIT_SERVICE, ctx, "Corte")
    
    # Tenta data inválida
    reply, state, ctx, _ = handle_message(State.WAIT_DATE, ctx, "não é uma data")
    assert state == State.WAIT_DATE
    assert "entender" in reply.lower() or "data" in reply.lower()


def test_invalid_time():
    """Testa validação de horário inválido."""
    ctx = {}
    
    # Chega até WAIT_TIME_PREF
    _, state, ctx, _ = handle_message(State.START, ctx, "Agendar")
    _, state, ctx, _ = handle_message(State.WAIT_BARBER, ctx, "João")
    _, state, ctx, _ = handle_message(State.WAIT_SERVICE, ctx, "Corte")
    tomorrow = (datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(days=1)).date()
    _, state, ctx, _ = handle_message(State.WAIT_DATE, ctx, f"{tomorrow.day}/{tomorrow.month}")
    
    # Tenta horário inválido
    reply, state, ctx, _ = handle_message(State.WAIT_TIME_PREF, ctx, "25:99")
    assert state == State.WAIT_TIME_PREF
    assert "entender" in reply.lower() or "horário" in reply.lower()


def test_intent_detection():
    """Testa detecção de intents."""
    # GREETING
    reply, state, _, _ = handle_message(State.START, {}, "Oi tudo bem?")
    assert "bem-vindo" in reply.lower() or "barbearia" in reply.lower()
    
    # BOOK_APPOINTMENT
    reply, state, _, _ = handle_message(State.START, {}, "Preciso agendar")
    assert state == State.WAIT_BARBER


def test_context_preservation():
    """Testa se contexto é preservado corretamente."""
    ctx = {}
    
    # Fluxo até ter contexto preenchido
    _, state, ctx, _ = handle_message(State.START, ctx, "Agendar")
    _, state, ctx, _ = handle_message(State.WAIT_BARBER, ctx, "João")
    
    # Verifica contexto
    context_obj = ConversationContext.from_dict(ctx)
    assert context_obj.barber_id == 1  # João é ID 1
    assert context_obj.barber_name == "João"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
