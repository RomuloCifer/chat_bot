def detect_intent(message: str) -> str:
    """
    Detecta a intenção do usuário na mensagem.
    
    Intents suportadas:
    - BOOKING: Agendar novo horário
    - CANCEL: Cancelar agendamento
    - REMARK: Remarcar agendamento existente
    - GREETING: Saudação
    - UNKNOWN: Não compreendido
    """
    msg = message.lower().strip()

    # === BOOK_APPOINTMENT ===
    book_keywords = [
        "agendar", "marcar", "marcação", "marcar horário", "horário", "horario",
        "quero agendar", "preciso agendar", "quer agendar", "quer marcar",
        "gostaria de marcar", "gostaria de agendar", "novo agendamento",
    ]
    if any(k in msg for k in book_keywords):
        return "BOOK_APPOINTMENT"

    # === CANCEL_APPOINTMENT ===
    cancel_keywords = [
        "cancelar", "desmarcar", "desmarcar horário", "cancelamento",
        "não vou", "não posso", "não dá", "nem vou", "esqueci",
        "marcar diferente", "outra data", "outro horário", "outro dia",
        "voltar", "recomeçar", "começar de novo",
    ]
    if any(k in msg for k in cancel_keywords):
        return "CANCEL_APPOINTMENT"

    # === REMARK_APPOINTMENT ===
    remark_keywords = [
        "remarcar", "mudar", "trocar", "alterar", "modificar", "adiar",
        "antecipar", "outra hora", "outro horário", "não é possível",
        "precisa mudar", "posso mudar", "acha que muda",
    ]
    if any(k in msg for k in remark_keywords):
        return "REMARK_APPOINTMENT"

    # === GREETING ===
    greeting_keywords = [
        "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
        "e aí", "eae", "tudo bem", "tudo certo", "opa", "oopa",
        "hey", "opa blz", "blz", "e ai", "tudo bem com você",
    ]
    if any(k in msg for k in greeting_keywords):
        return "GREETING"

    # === UNKNOWN ===
    return "UNKNOWN"
