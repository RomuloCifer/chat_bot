from app.services.nlu import detect_intent
from app.repositories.barbers_repo import list_active_barbers, find_barber_by_name
from app.repositories.services_repo import list_active_services, find_service_by_name
from app.domain.enums import State
from app.services.parsers import parse_br_date


def handle_message(current_state: str, ctx: dict, message: str) -> tuple[str, str, dict, list]:
    msg = message.strip()

    # START
    if current_state == State.START:
        intent = detect_intent(msg)

        if intent == "GREETING":
            return (
                "Olá! 👋 Posso te ajudar a agendar, remarcar ou cancelar um horário.",
                State.START,
                ctx,
                [],
            )

        if intent == "BOOK_APPOINTMENT":
            barbers = list_active_barbers()
            return (
                "Perfeito! Com qual barbeiro você prefere agendar?",
                State.WAIT_BARBER,
                ctx,
                [{"id": f"BARBER_{b['id']}", "label": b["name"]} for b in barbers],
            )

        return (
            "Não entendi muito bem 😅\nVocê pode dizer se quer agendar ou cancelar?",
            State.START,
            ctx,
            [],
        )

    # WAIT_BARBER
    if current_state == State.WAIT_BARBER:
        barber = find_barber_by_name(msg)

        if not barber:
            barbers = list_active_barbers()
            return (
                "Não encontrei esse barbeiro 😕\nEscolha uma das opções:",
                State.WAIT_BARBER,
                ctx,
                [{"id": f"BARBER_{b['id']}", "label": b["name"]} for b in barbers],
            )

        ctx["barber_id"] = barber["id"]
        ctx["barber_name"] = barber["name"]

        return (
            f"Show! {barber['name']} escolhido 👍\nAgora, qual serviço você deseja?",
            State.WAIT_SERVICE,
            ctx,
            [{"id": f"SERVICE_{s['id']}", "label": f"{s['name']} ({s['duration_minutes']}min)"} for s in list_active_services()],
        )

    # WAIT_SERVICE
    if current_state == State.WAIT_SERVICE:
        service = find_service_by_name(msg)

        if not service:
            services = list_active_services()
            return (
                "Qual serviço você deseja?",
                State.WAIT_SERVICE,
                ctx,
                [{"id": f"SERVICE_{s['id']}", "label": f"{s['name']} ({s['duration_minutes']}min)"} for s in services],
            )

        ctx["service_id"] = service["id"]
        ctx["service_name"] = service["name"]
        ctx["service_duration_minutes"] = service["duration_minutes"]

        return (
            f"Fechado! Serviço: {service['name']} ({service['duration_minutes']}min).\nAgora me diga o dia que você quer (ex: 20/01).",
            "WAIT_DATE",
            ctx,
            [],
        )
    if current_state == State.WAIT_DATE:
        d = parse_br_date(msg)

        if not d:
            return (
            "Não consegui entender a data 😅\nMe diga assim: 20/01 (ou 20/01/2026).",
            State.WAIT_DATE,
            ctx,
            [],
        )

        ctx["date"] = d.isoformat()  # "YYYY-MM-DD"

        return (
        f"Show! Dia {d.strftime('%d/%m')}.\nAgora me diga um horário aproximado (ex: 14:00).",
        "WAIT_TIME_PREF",
        ctx,
        [],
    )


    return ("Vamos continuar 🙂", current_state, ctx, [])
