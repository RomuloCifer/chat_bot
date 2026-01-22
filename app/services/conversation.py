from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.nlu import detect_intent
from app.repositories.barbers_repo import list_active_barbers, find_barber_by_name, find_barber_by_id
from app.repositories.services_repo import list_active_services, find_service_by_name, find_service_by_id
from app.repositories.appointments_repo import create_appointment, list_appointments_for_client, cancel_appointment
from app.repositories.clients_repo import get_client_by_key
from app.domain.enums import State
from app.domain.models import ConversationContext
from app.services.parsers import parse_br_date, parse_br_time
from app.services.availability import generate_suggestions
from app.core.logging import get_logger

logger = get_logger(__name__)


def handle_message(current_state: str, ctx: dict, message: str) -> tuple[str, str, dict, list]:
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
    ctx = ConversationContext.from_dict(ctx)

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
            # Requer client_key para identificar cliente
            client_key = getattr(ctx, "client_key", None) or (ctx.to_dict().get("client_key"))
            if not client_key:
                return (
                    "Não consegui identificar você. Pode tentar novamente?",
                    State.START,
                    ctx.to_dict(),
                    [],
                )

            client_row = get_client_by_key(client_key)
            if not client_row:
                return (
                    "Não encontrei seu cadastro. Vamos começar do zero?",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )

            appts = list_appointments_for_client(int(client_row["id"]), status="scheduled")
            # Filtra próximos (>= agora) quando possível
            now_iso = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
            upcoming = [a for a in appts if a["start_at"] >= now_iso]
            if not upcoming:
                return (
                    "Você não tem agendamentos ativos para alterar/cancelar.",
                    State.START,
                    ctx.to_dict(),
                    [],
                )

            # Botões de escolha quando > 1
            def _label(a: dict) -> str:
                # Monta label com data/hora e barbeiro
                bname = None
                try:
                    b = find_barber_by_id(int(a["barber_id"]))
                    bname = b["name"] if b else None
                except Exception:
                    bname = None
                dt = a["start_at"][11:16]  # HH:MM
                d = a["start_at"][8:10] + "/" + a["start_at"][5:7]
                return f"{d} {dt}" + (f" · {bname}" if bname else "")

            if len(upcoming) > 1:
                buttons = [{"id": f"APPT_{a['id']}", "label": _label(a)} for a in upcoming]
                ctx.operation = "cancel" if intent == "CANCEL_APPOINTMENT" else "remark"
                return (
                    "Qual agendamento você quer alterar?",
                    State.WAIT_APPOINTMENT_PICK,
                    ctx.to_dict(),
                    buttons,
                )

            # Se houver só um, segue direto
            target = upcoming[0]
            if intent == "CANCEL_APPOINTMENT":
                ctx.operation = "cancel"
                ctx.cancel_appt_id = int(target["id"])
                return (
                    f"Confirmar cancelamento do horário de {target['start_at'][8:10]}/{target['start_at'][5:7]} às {target['start_at'][11:16]}?",
                    State.WAIT_CANCEL_CONFIRMATION,
                    ctx.to_dict(),
                    [
                        {"id": "CANCEL_YES", "label": "Sim, cancelar"},
                        {"id": "CANCEL_NO", "label": "Não, voltar"},
                    ],
                )
            else:
                ctx.operation = "remark"
                ctx.remark_appt_id = int(target["id"])
                # Prefill barber/service
                ctx.barber_id = int(target["barber_id"])
                b = find_barber_by_id(ctx.barber_id)
                ctx.barber_name = b["name"] if b else None
                ctx.service_id = int(target["service_id"])
                s = find_service_by_id(ctx.service_id)
                if s:
                    ctx.service_name = s["name"]
                    ctx.service_duration_minutes = int(s["duration_minutes"])
                return (
                    "Certo, vamos remarcar. Me diga o novo dia (ex: 21/01).",
                    State.WAIT_REMARK_DATE,
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

    # === WAIT_REMARK_DATE ===
    if current_state == State.WAIT_REMARK_DATE:
        d = parse_br_date(msg)
        if not d:
            return (
                "Não consegui entender a data 😅\nMe diga assim: 20/01 (ou 20/01/2026).",
                State.WAIT_REMARK_DATE,
                ctx.to_dict(),
                [],
            )
        ctx.date = d.isoformat()
        return (
            f"Show! Dia {d.strftime('%d/%m')}\nAgora me diga um horário aproximado (ex: 14:00).",
            State.WAIT_REMARK_TIME_PREF,
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

        # Suporta clique de botão (id: SLOT_HH:MM) ou entrada livre "HH:MM"
        parsed_msg = msg.strip()
        if parsed_msg.upper().startswith("SLOT_"):
            parsed_msg = parsed_msg.split("_", 1)[1]
        t = parse_br_time(parsed_msg)
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

        # Verifica se o horário exato solicitado está disponível (é o primeiro sugerido)
        ctx.time_pref = t.strftime("%H:%M")
        date_obj = datetime.fromisoformat(ctx.date).date()
        chosen_start = datetime.combine(date_obj, t, tzinfo=tz)
        
        if suggestions[0].strftime("%H:%M") == chosen_start.strftime("%H:%M"):
            # Horário exato disponível! Vai direto pra confirmação
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
        
        # Horário não está disponível, oferece aproximados
        buttons = [
            {"id": f"SLOT_{s.strftime('%H:%M')}", "label": s.strftime("%H:%M")}
            for s in suggestions
        ]

        return (
            "Esse horário não está disponível. Posso sugerir estes:",
            State.WAIT_SLOT_PICK,
            ctx.to_dict(),
            buttons,
        )

    # === WAIT_REMARK_TIME_PREF === (semelhante ao WAIT_TIME_PREF)
    if current_state == State.WAIT_REMARK_TIME_PREF:
        parsed_msg = msg.strip()
        if parsed_msg.upper().startswith("SLOT_"):
            parsed_msg = parsed_msg.split("_", 1)[1]
        t = parse_br_time(parsed_msg)
        if not t:
            return (
                "Não entendi o horário 😅\nMe diga assim: 14:00 (ou 14h).",
                State.WAIT_REMARK_TIME_PREF,
                ctx.to_dict(),
                [],
            )
        if not ctx.date or not ctx.barber_id or not ctx.service_duration_minutes:
            return (
                "Ops, perdi o contexto. Vamos começar de novo.",
                State.START,
                ConversationContext().to_dict(),
                [],
            )
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
                State.WAIT_REMARK_DATE,
                ctx.to_dict(),
                [],
            )
        
        # Verifica se o horário exato está disponível (remarcação)
        ctx.time_pref = t.strftime("%H:%M")
        date_obj = datetime.fromisoformat(ctx.date).date()
        chosen_start = datetime.combine(date_obj, t, tzinfo=tz)
        
        if suggestions[0].strftime("%H:%M") == chosen_start.strftime("%H:%M"):
            # Horário exato disponível! Vai direto pra confirmação
            ctx.selected_slot = t.strftime("%H:%M")
            return (
                f"Vou remarcar para {ctx.barber_name}, {ctx.service_name} no dia {ctx.date} às {ctx.selected_slot}. Confirmar?",
                State.WAIT_REMARK_CONFIRMATION,
                ctx.to_dict(),
                [
                    {"id": "REMARK_YES", "label": "Sim, remarcar"},
                    {"id": "REMARK_NO", "label": "Não, voltar"},
                ],
            )
        
        # Horário não está disponível, oferece aproximados
        buttons = [
            {"id": f"SLOT_{s.strftime('%H:%M')}", "label": s.strftime("%H:%M")}
            for s in suggestions
        ]
        return (
            "Esse horário não está disponível. Posso sugerir estes:",
            State.WAIT_REMARK_SLOT_PICK,
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

        # Valida contexto mínimo
        if not ctx.date or not ctx.barber_id or not ctx.service_id or not ctx.service_duration_minutes:
            return (
                "Ops, perdi o contexto do agendamento. Vamos começar de novo.",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

        tz = ZoneInfo("America/Sao_Paulo")
        date_obj = datetime.fromisoformat(ctx.date).date()
        chosen_start = datetime.combine(date_obj, t, tzinfo=tz)
        # Gera sugestões a partir do horário escolhido
        suggestions = generate_suggestions(
            date_iso=ctx.date,
            barber_id=int(ctx.barber_id),
            duration_minutes=int(ctx.service_duration_minutes),
            preferred_time=t,
            tz=tz,
            max_suggestions=3,
        )

        # Se o primeiro sugerido for exatamente o horário escolhido, considera livre
        if suggestions and suggestions[0].strftime("%H:%M") == chosen_start.strftime("%H:%M"):
            # Se tivermos client_key no contexto, efetiva o agendamento
            client_key = getattr(ctx, "client_key", None) or (ctx.to_dict().get("client_key"))
            if client_key:
                client_row = get_client_by_key(client_key)
                if client_row:
                    client_id = int(client_row["id"])
                    start_dt = chosen_start
                    end_dt = start_dt + timedelta(minutes=int(ctx.service_duration_minutes))
                    try:
                        create_appointment(
                            client_id=client_id,
                            barber_id=int(ctx.barber_id),
                            service_id=int(ctx.service_id),
                            start_at=start_dt.isoformat(),
                            end_at=end_dt.isoformat(),
                        )
                        return (
                            f"✅ Agendamento confirmado!\n{ctx.barber_name} - {ctx.service_name}\n{ctx.date} às {start_dt.strftime('%H:%M')}\nAté logo! 😊",
                            State.CONFIRMED,
                            ctx.to_dict(),
                            [],
                        )
                    except Exception as e:
                        logger.error(f"Erro ao criar agendamento: {e}", exc_info=True)
                        # fallback para confirmação manual

            # Sem client_key ou erro: pede confirmação manual
            ctx.selected_slot = chosen_start.strftime("%H:%M")
            return (
                f"Perfeito! Vou agendar para {ctx.barber_name}, {ctx.service_name} no dia {ctx.date} às {ctx.selected_slot}.\nConfirma? (sim/não)",
                State.WAIT_CONFIRMATION,
                ctx.to_dict(),
                [
                    {"id": "CONFIRM_YES", "label": "Sim, confirmar"},
                    {"id": "CONFIRM_NO", "label": "Não, voltar"},
                ],
            )

        # Caso o horário escolhido não esteja disponível, sugere próximos (-30, +30, ...)
        alt_buttons = [
            {"id": f"SLOT_{s.strftime('%H:%M')}", "label": s.strftime("%H:%M")}
            for s in suggestions[:2]
        ] if suggestions else []

        if not alt_buttons:
            return (
                "Não consegui encontrar alternativas próximas. Quer tentar outro dia?",
                State.WAIT_DATE,
                ctx.to_dict(),
                [],
            )

        return (
            "Esse horário não está disponível. Posso sugerir estes:",
            State.WAIT_SLOT_PICK,
            ctx.to_dict(),
            alt_buttons,
        )

    # === WAIT_REMARK_SLOT_PICK === (semelhante ao WAIT_SLOT_PICK)
    if current_state == State.WAIT_REMARK_SLOT_PICK:
        t = parse_br_time(msg)
        if not t:
            return (
                "Horário inválido. Escolha um dos horários sugeridos acima.",
                State.WAIT_REMARK_SLOT_PICK,
                ctx.to_dict(),
                [],
            )
        if not ctx.date or not ctx.barber_id or not ctx.service_id or not ctx.service_duration_minutes:
            return (
                "Ops, perdi o contexto. Vamos começar de novo.",
                State.START,
                ConversationContext().to_dict(),
                [],
            )
        tz = ZoneInfo("America/Sao_Paulo")
        date_obj = datetime.fromisoformat(ctx.date).date()
        chosen_start = datetime.combine(date_obj, t, tzinfo=tz)
        suggestions = generate_suggestions(
            date_iso=ctx.date,
            barber_id=int(ctx.barber_id),
            duration_minutes=int(ctx.service_duration_minutes),
            preferred_time=t,
            tz=tz,
            max_suggestions=3,
        )
        if suggestions and suggestions[0].strftime("%H:%M") == chosen_start.strftime("%H:%M"):
            ctx.selected_slot = chosen_start.strftime("%H:%M")
            return (
                f"Vou remarcar para {ctx.barber_name}, {ctx.service_name} no dia {ctx.date} às {ctx.selected_slot}. Confirmar?",
                State.WAIT_REMARK_CONFIRMATION,
                ctx.to_dict(),
                [
                    {"id": "REMARK_YES", "label": "Sim, remarcar"},
                    {"id": "REMARK_NO", "label": "Não, voltar"},
                ],
            )
        alt_buttons = [
            {"id": f"SLOT_{s.strftime('%H:%M')}", "label": s.strftime("%H:%M")}
            for s in suggestions[:2]
        ] if suggestions else []
        if not alt_buttons:
            return (
                "Não consegui encontrar alternativas próximas. Quer tentar outro dia?",
                State.WAIT_REMARK_DATE,
                ctx.to_dict(),
                [],
            )
        return (
            "Esse horário não está disponível. Posso sugerir estes:",
            State.WAIT_REMARK_SLOT_PICK,
            ctx.to_dict(),
            alt_buttons,
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

    # === WAIT_CANCEL_CONFIRMATION ===
    if current_state == State.WAIT_CANCEL_CONFIRMATION:
        if any(x in msg.lower() for x in ["sim", "confirmar", "yes", "confirm"]) or intent == "CANCEL_APPOINTMENT":
            if not ctx.cancel_appt_id:
                return (
                    "Não encontrei o agendamento alvo. Vamos começar de novo.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )
            try:
                cancel_appointment(int(ctx.cancel_appt_id))
                return (
                    "✅ Agendamento cancelado com sucesso.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )
            except Exception as e:
                logger.error(f"Erro ao cancelar agendamento: {e}", exc_info=True)
                return (
                    "Não consegui cancelar agora. Tente mais tarde.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )
        else:
            return (
                "Cancelamento abortado. Posso ajudar com outra coisa?",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

    # === WAIT_REMARK_CONFIRMATION ===
    if current_state == State.WAIT_REMARK_CONFIRMATION:
        if any(x in msg.lower() for x in ["sim", "confirmar", "yes", "confirm"]) or intent == "REMARK_APPOINTMENT":
            # Precisa de remark_appt_id + client_key + barber/service + date + selected_slot
            if not (ctx.remark_appt_id and ctx.barber_id and ctx.service_id and ctx.date and ctx.selected_slot):
                return (
                    "Dados incompletos para remarcar. Vamos começar de novo.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )
            client_key = getattr(ctx, "client_key", None) or (ctx.to_dict().get("client_key"))
            if not client_key:
                return (
                    "Não consegui identificar você. Vamos começar de novo.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )
            client_row = get_client_by_key(client_key)
            if not client_row:
                return (
                    "Não encontrei seu cadastro. Vamos começar de novo.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )
            try:
                tz = ZoneInfo("America/Sao_Paulo")
                date_obj = datetime.fromisoformat(ctx.date).date()
                slot_obj = datetime.strptime(ctx.selected_slot, "%H:%M").time()
                start_dt = datetime.combine(date_obj, slot_obj, tzinfo=tz)
                end_dt = start_dt + timedelta(minutes=int(ctx.service_duration_minutes))
                # Cancela o antigo
                cancel_appointment(int(ctx.remark_appt_id))
                # Cria novo
                create_appointment(
                    client_id=int(client_row["id"]),
                    barber_id=int(ctx.barber_id),
                    service_id=int(ctx.service_id),
                    start_at=start_dt.isoformat(),
                    end_at=end_dt.isoformat(),
                )
                return (
                    f"✅ Horário remarcado! {ctx.barber_name} - {ctx.service_name}\n{ctx.date} às {ctx.selected_slot}",
                    State.CONFIRMED,
                    ConversationContext().to_dict(),
                    [],
                )
            except Exception as e:
                logger.error(f"Erro ao remarcar: {e}", exc_info=True)
                return (
                    "Não consegui remarcar agora. Tente novamente.",
                    State.START,
                    ConversationContext().to_dict(),
                    [],
                )
        else:
            return (
                "Remarcação cancelada. Posso ajudar com outra coisa?",
                State.START,
                ConversationContext().to_dict(),
                [],
            )

    # === WAIT_APPOINTMENT_PICK ===
    if current_state == State.WAIT_APPOINTMENT_PICK:
        # Espera um id do tipo APPT_<id>
        if msg.upper().startswith("APPT_"):
            try:
                appt_id = int(msg.split("_", 1)[1])
            except Exception:
                appt_id = None
            if not appt_id:
                return (
                    "Seleção inválida. Tente novamente.",
                    State.WAIT_APPOINTMENT_PICK,
                    ctx.to_dict(),
                    [],
                )
            if ctx.operation == "cancel":
                ctx.cancel_appt_id = appt_id
                return (
                    "Confirmar cancelamento deste agendamento?",
                    State.WAIT_CANCEL_CONFIRMATION,
                    ctx.to_dict(),
                    [
                        {"id": "CANCEL_YES", "label": "Sim, cancelar"},
                        {"id": "CANCEL_NO", "label": "Não, voltar"},
                    ],
                )
            # remark
            ctx.remark_appt_id = appt_id
            # Para preencher barber/service, precisamos buscar o agendamento
            client_key = getattr(ctx, "client_key", None) or (ctx.to_dict().get("client_key"))
            client_row = get_client_by_key(client_key) if client_key else None
            if client_row:
                appts = list_appointments_for_client(int(client_row["id"]), status="scheduled")
                target = next((a for a in appts if int(a["id"]) == appt_id), None)
                if target:
                    ctx.barber_id = int(target["barber_id"])
                    b = find_barber_by_id(ctx.barber_id)
                    ctx.barber_name = b["name"] if b else None
                    ctx.service_id = int(target["service_id"])
                    s = find_service_by_id(ctx.service_id)
                    if s:
                        ctx.service_name = s["name"]
                        ctx.service_duration_minutes = int(s["duration_minutes"])
            return (
                "Certo, vamos remarcar. Me diga o novo dia (ex: 21/01).",
                State.WAIT_REMARK_DATE,
                ctx.to_dict(),
                [],
            )
        # fallback
        return (
            "Escolha um dos agendamentos listados.",
            State.WAIT_APPOINTMENT_PICK,
            ctx.to_dict(),
            [],
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

