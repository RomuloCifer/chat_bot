from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.nlu import detect_intent
from app.repositories.barbers_repo import list_active_barbers, find_barber_by_name
from app.repositories.services_repo import list_active_services, find_service_by_name
from app.repositories.appointments_repo import create_appointment, list_appointments_for_client
from app.repositories.clients_repo import get_client_by_key
from app.domain.enums import State
from app.domain.models import ConversationContext
from app.services.parsers import parse_br_date, parse_br_time
from app.services.availability import generate_suggestions
from app.core.logging import get_logger

logger = get_logger(__name__)


def handle_message(current_state: str, ctx_dict: dict, message: str) -> tuple[str, str, dict, list]:
    """
    Máquina de estados de conversação.

    Args:
        current_state: Estado atual (START, WAIT_BARBER, etc)
        ctx_dict: Contexto em formato dict (será convertido para ConversationContext)
        message: Mensagem do usuário

    Returns:
        (reply: str, next_state: str, next_ctx_dict: dict, buttons: list[dict])
    """
    msg = message.strip()
    logger.debug(f"State: {current_state} | Input: {msg}")

    # Reconstrói contexto tipado
    ctx = ConversationContext.from_dict(ctx_dict)

    # Detecta intent genérico (pode ser usado em qualquer estado)
    intent = detect_intent(msg)
    logger.debug(f"Detected intent: {intent}")

    # === START ===
    if current_state == State.START:
        if intent == "GREETING":
            return (
                "Olá! 👋 Bem-vindo à barbearia! Posso te ajudar a agendar, remarcar ou cancelar um horário.",
                State.START,
                ctx.to_dict(),
                [],
            )

        if intent == "BOOK_APPOINTMENT":
            barbers = list_active_barbers()
            return (
                "Perfeito! Com qual barbeiro você prefere agendar?",
                State.WAIT_BARBER,
                ctx.to_dict(),
                [{"id": f"BARBER_{b['id']}", "label": b["name"]} for b in barbers],
            )

        if intent in ["CANCEL_APPOINTMENT", "REMARK_APPOINTMENT"]:
            return (
                "Entendi. Para isso, você precisa ter um agendamento ativo. Deixa eu buscar aqui...",
                State.WAIT_CLARIFICATION,
                ctx.to_dict(),
                [],
            )

        return (
            "Não entendi muito bem 😅\nVocê pode dizer se quer agendar, remarcar ou cancelar?",
            State.START,
            ctx.to_dict(),
            [],
        )

    # === WAIT_BARBER ===
    if current_state == State.WAIT_BARBER:
        # Permite atalho para voltar
        if intent == "CANCEL_APPOINTMENT":
            return (
                "Tudo bem, voltamos ao início! 👋",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

        barber = find_barber_by_name(msg)
        if not barber:
            barbers = list_active_barbers()
            return (
                "Não encontrei esse barbeiro 😕\nEscolha uma das opções abaixo:",
                State.WAIT_BARBER,
                ctx.to_dict(),
                [{"id": f"BARBER_{b['id']}", "label": b["name"]} for b in barbers],
            )

        ctx.barber_id = barber["id"]
        ctx.barber_name = barber["name"]

        services = list_active_services()
        return (
            f"Show! {barber['name']} escolhido 👍\nAgora, qual serviço você deseja?",
            State.WAIT_SERVICE,
            ctx.to_dict(),
            [{"id": f"SERVICE_{s['id']}", "label": f"{s['name']} ({s['duration_minutes']}min)"} for s in services],
        )

    # === WAIT_SERVICE ===
    if current_state == State.WAIT_SERVICE:
        if intent == "CANCEL_APPOINTMENT":
            return (
                "Tudo bem, voltamos ao início! 👋",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

        service = find_service_by_name(msg)
        if not service:
            services = list_active_services()
            return (
                "Qual serviço você deseja?",
                State.WAIT_SERVICE,
                ctx.to_dict(),
                [{"id": f"SERVICE_{s['id']}", "label": f"{s['name']} ({s['duration_minutes']}min)"} for s in services],
            )

        ctx.service_id = service["id"]
        ctx.service_name = service["name"]
        ctx.service_duration_minutes = service["duration_minutes"]

        return (
            f"Fechado! Serviço: {service['name']} ({service['duration_minutes']}min).\nAgora me diga o dia que você quer (ex: 20/01).",
            State.WAIT_DATE,
            ctx.to_dict(),
            [],
        )

    # === WAIT_DATE ===
    if current_state == State.WAIT_DATE:
        if intent == "CANCEL_APPOINTMENT":
            return (
                "Tudo bem, voltamos ao início! 👋",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

        d = parse_br_date(msg)
        if not d:
            return (
                "Não consegui entender a data 😅\nMe diga assim: 20/01 (ou 20/01/2026).",
                State.WAIT_DATE,
                ctx.to_dict(),
                [],
            )

        ctx.date = d.isoformat()  # "YYYY-MM-DD"
        return (
            f"Show! Dia {d.strftime('%d/%m')}.\nAgora me diga um horário aproximado (ex: 14:00).",
            State.WAIT_TIME_PREF,
            ctx.to_dict(),
            [],
        )

    # === WAIT_TIME_PREF ===
    if current_state == State.WAIT_TIME_PREF:
        if intent == "CANCEL_APPOINTMENT":
            return (
                "Tudo bem, voltamos ao início! 👋",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

        t = parse_br_time(msg)
        if not t:
            return (
                "Não entendi o horário 😅\nMe diga assim: 14:00 (ou 14h).",
                State.WAIT_TIME_PREF,
                ctx.to_dict(),
                [],
            )

        # Valida contexto
        if not ctx.date or not ctx.barber_id or not ctx.service_duration_minutes:
            return (
                "Ops, perdi o contexto do agendamento. Vamos começar de novo.",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

        # Gera sugestões de horários
        tz = ZoneInfo("America/Sao_Paulo")
        suggestions = generate_suggestions(
            date_iso=ctx.date,
            barber_id=int(ctx.barber_id),
            duration_minutes=int(ctx.service_duration_minutes),
            preferred_time=t,
            tz=tz,
            max_suggestions=3,
        )

        if not suggestions:
            return (
                "Não achei horários disponíveis nesse dia 😕\nQuer tentar outro dia? (ex: 21/01)",
                State.WAIT_DATE,
                ctx.to_dict(),
                [],
            )

        ctx.time_pref = t.strftime("%H:%M")
        buttons = [
            {"id": f"SLOT_{s.strftime('%H:%M')}", "label": s.strftime("%H:%M")}
            for s in suggestions
        ]

        return (
            "Tenho esses horários disponíveis. Qual você prefere?",
            State.WAIT_SLOT_PICK,
            ctx.to_dict(),
            buttons,
        )

    # === WAIT_SLOT_PICK ===
    if current_state == State.WAIT_SLOT_PICK:
        if intent == "CANCEL_APPOINTMENT":
            return (
                "Tudo bem, voltamos ao início! 👋",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

        t = parse_br_time(msg)
        if not t:
            return (
                "Horário inválido. Escolha um dos horários sugeridos acima.",
                State.WAIT_SLOT_PICK,
                ctx.to_dict(),
                [],
            )

        ctx.selected_slot = t.strftime("%H:%M")
        return (
            f"Perfeito! Vou agendar para {ctx.barber_name}, {ctx.service_name} no dia {ctx.date} às {ctx.selected_slot}.\nConfirma? (sim/não)",
            State.WAIT_CONFIRMATION,
            ctx.to_dict(),
            [
                {"id": "CONFIRM_YES", "label": "Sim, confirmar"},
                {"id": "CONFIRM_NO", "label": "Não, voltar"},
            ],
        )

    # === WAIT_CONFIRMATION ===
    if current_state == State.WAIT_CONFIRMATION:
        # Aceita sim/não/confirmar/cancelar
        if intent in ["BOOK_APPOINTMENT"] or "sim" in msg.lower():
            # Cria agendamento
            if not ctx.is_complete_for_booking():
                return (
                    "Ops, dados incompletos. Vamos começar de novo.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )

            try:
                # Cria os datetimes em ISO com timezone
                tz = ZoneInfo("America/Sao_Paulo")
                date_obj = datetime.fromisoformat(ctx.date).date()
                slot_obj = datetime.strptime(ctx.selected_slot, "%H:%M").time()
                start_dt = datetime.combine(date_obj, slot_obj, tzinfo=tz)
                end_dt = start_dt.replace(tzinfo=tz) + __import__('datetime').timedelta(
                    minutes=ctx.service_duration_minutes
                )

                # Nota: client_id será passado pela route
                # Aqui só retornamos a confirmação
                return (
                    f"✅ Agendamento confirmado!\n{ctx.barber_name} - {ctx.service_name}\n{ctx.date} às {ctx.selected_slot}\nAté logo! 😊",
                    State.CONFIRMED,
                    ctx.to_dict(),
                    [],
                )

            except Exception as e:
                return (
                    f"Ops, erro ao agendar: {str(e)}. Tente de novo.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )

        elif "não" in msg.lower() or intent == "CANCEL_APPOINTMENT":
            return (
                "Tudo bem, vamos voltar! Qual barbeiro você prefere?",
                State.WAIT_BARBER,
                ConversationContext.from_dict(
                    {
                        "barber_id": ctx.barber_id,
                        "barber_name": ctx.barber_name,
                    }
                ).to_dict(),
                [{"id": f"BARBER_{b['id']}", "label": b["name"]} for b in list_active_barbers()],
            )

        return (
            "Por favor, confirma o agendamento: sim ou não?",
            State.WAIT_CONFIRMATION,
            ctx.to_dict(),
            [
                {"id": "CONFIRM_YES", "label": "Sim"},
                {"id": "CONFIRM_NO", "label": "Não"},
            ],
        )

    # === WAIT_CLARIFICATION ===
    if current_state == State.WAIT_CLARIFICATION:
        return (
            "Como você pode me ajudar?",
            State.START,
            ConversationContext().to_dict(),
            [],
        )

    # === CONFIRMED ===
    if current_state == State.CONFIRMED:
        return (
            "O agendamento já foi confirmado! Quer fazer mais algo?",
            State.START,
            ConversationContext().to_dict(),
            [],
        )

    # === Estado desconhecido ===
    return (
        "Algo deu errado. Vamos começar de novo!",
        State.START,
        ConversationContext().to_dict(),
        [],
    )

