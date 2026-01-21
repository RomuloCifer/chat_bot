def detect_intent(message: str) -> str:
    msg = message.lower().strip()

    if any(k in msg for k in ["agendar", "marcar", "horário", "horario"]):
        return "BOOK_APPOINTMENT"

    if any(k in msg for k in ["cancelar", "desmarcar"]):
        return "CANCEL_APPOINTMENT"

    if any(k in msg for k in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
        return "GREETING"

    return "UNKNOWN"
