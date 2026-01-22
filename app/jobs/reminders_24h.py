"""
Lógica de envio de reminders D-1 (1 dia antes do agendamento).

Responsabilidades:
- Buscar agendamentos com start_at no intervalo [amanhã 00:00, amanhã 23:59]
- Para cada cliente, enviar lembrete pedindo confirmação ou cancelamento
- Marcar como reminder_sent para evitar duplicata
- Suportar web chat e WhatsApp (abstração de canal)
"""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from app.repositories.appointments_repo import (
    list_appointments_for_barber_on_date,
    get_appointment_by_id,
)
from app.repositories.clients_repo import get_client_by_key, set_client_state_and_ctx
from app.repositories.barbers_repo import find_barber_by_id
from app.repositories.services_repo import find_service_by_id
from app.repositories.db import get_conn
from app.core.logging import get_logger
from app.domain.enums import State

logger = get_logger(__name__)


def list_appointments_for_reminder(tz: ZoneInfo) -> list[dict]:
    """
    Lista agendamentos que devem receber lembrete amanhã.
    
    Critérios:
    - status = 'scheduled'
    - start_at está entre amanhã 00:00 e amanhã 23:59
    - reminder_sent_at IS NULL (ainda não foi enviado)
    
    Args:
        tz: Timezone (ex: America/Sao_Paulo)
    
    Returns:
        Lista de appointments com os dados completos
    """
    conn = get_conn()
    try:
        now = datetime.now(tz)
        tomorrow = now + timedelta(days=1)
        tomorrow_start = datetime.combine(tomorrow.date(), time.min, tzinfo=tz).isoformat()
        tomorrow_end = datetime.combine(tomorrow.date(), time.max, tzinfo=tz).isoformat()
        
        rows = conn.execute(
            """
            SELECT id, client_id, barber_id, service_id, start_at, end_at, status, reminder_sent_at,
                   created_at, updated_at
            FROM appointments
            WHERE status = 'scheduled'
              AND start_at >= ?
              AND start_at <= ?
              AND reminder_sent_at IS NULL
            ORDER BY start_at
            """,
            (tomorrow_start, tomorrow_end),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_reminder_sent(appointment_id: int) -> None:
    """
    Marca que o lembrete foi enviado para um agendamento.
    
    Args:
        appointment_id: ID do agendamento
    """
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE appointments
            SET reminder_sent_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ?
            """,
            (appointment_id,),
        )
        conn.commit()
    finally:
        conn.close()


def format_reminder_message(appointment: dict, tz: ZoneInfo) -> str:
    """
    Formata a mensagem de lembrete para o cliente.
    
    Args:
        appointment: Dict com id, barber_id, start_at, etc
        tz: Timezone
    
    Returns:
        Mensagem formatada
    """
    try:
        barber = find_barber_by_id(int(appointment["barber_id"]))
        barber_name = barber["name"] if barber else "Barbeiro"
        
        service = find_service_by_id(int(appointment["service_id"]))
        service_name = service["name"] if service else "Serviço"
        
        # Parse datetime
        dt = datetime.fromisoformat(appointment["start_at"])
        date_str = dt.strftime("%d/%m")
        time_str = dt.strftime("%H:%M")
        
        message = f"""🔔 Lembrete de agendamento!

Seu horário é amanhã ({date_str}) às {time_str}
Barbeiro: {barber_name}
Serviço: {service_name}

Confirma presença ou cancela? 
Responda com SIM para confirmar ou NÃO para cancelar."""
        
        return message
    except Exception as e:
        logger.error(f"Erro ao formatar mensagem: {e}")
        return "🔔 Você tem um agendamento amanhã. Confirma presença?"


async def send_reminder_to_client(
    client_key: str,
    appointment: dict,
    tz: ZoneInfo,
) -> bool:
    """
    Envia um lembrete para um cliente (abstração de canal).
    
    Por enquanto, apenas loga a intenção (mock).
    Futura integração: enviar via email/SMS/WhatsApp conforme channel.
    
    Args:
        client_key: Identificador do cliente (ex: user_123 ou wa:5511987654321)
        appointment: Dict com dados do agendamento
        tz: Timezone
    
    Returns:
        True se enviado com sucesso
    """
    try:
        message = format_reminder_message(appointment, tz)
        logger.info(f"[REMINDER] Enviando para {client_key}: {message[:50]}...")
        
        # TODO: Implementar envio real (email, SMS, WhatsApp, etc)
        # Por enquanto, apenas marca como enviado
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar lembrete para {client_key}: {e}")
        return False


async def run_reminders_job(tz: ZoneInfo = None) -> None:
    """
    Job principal: busca agendamentos para amanhã e envia lembretes.
    
    Fluxo:
    1. Lista agendamentos de amanhã (sem reminder_sent)
    2. Para cada um, busca cliente e envia lembrete
    3. Marca como reminder_sent para evitar duplicata
    
    Args:
        tz: Timezone (default: America/Sao_Paulo)
    """
    if not tz:
        tz = ZoneInfo("America/Sao_Paulo")
    
    logger.info("[REMINDERS] Iniciando job de lembretes D-1...")
    
    try:
        appointments = list_appointments_for_reminder(tz)
        logger.info(f"[REMINDERS] Encontrados {len(appointments)} agendamentos para amanhã")
        
        success_count = 0
        for appt in appointments:
            try:
                client_id = int(appt["client_id"])
                client_row = get_client_by_key(f"user_{client_id}")  # Web chat
                
                if not client_row:
                    # Tenta buscar para WhatsApp mais tarde (versão futura)
                    logger.warning(f"Cliente {client_id} não encontrado")
                    continue
                
                client_key = client_row["client_key"]
                
                # Envia lembrete
                sent = await send_reminder_to_client(client_key, appt, tz)
                if sent:
                    mark_reminder_sent(int(appt["id"]))
                    success_count += 1
                    logger.info(f"[REMINDERS] Lembrete enviado: appt_id={appt['id']}, client_key={client_key}")
                else:
                    logger.warning(f"[REMINDERS] Falha ao enviar para appt_id={appt['id']}")
            
            except Exception as e:
                logger.error(f"[REMINDERS] Erro ao processar agendamento {appt.get('id')}: {e}", exc_info=True)
        
        logger.info(f"[REMINDERS] Job concluído: {success_count}/{len(appointments)} lembretes enviados")
    
    except Exception as e:
        logger.error(f"[REMINDERS] Erro geral no job: {e}", exc_info=True)
