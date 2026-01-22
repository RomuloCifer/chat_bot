"""
Agendador de jobs com APScheduler.

Responsabilidades:
- Inicializar APScheduler
- Registrar jobs periódicos (lembretes D-1, etc)
- Fornecer CLI para start/stop
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
from zoneinfo import ZoneInfo

from app.core.logging import get_logger
from app.jobs.reminders_24h import run_reminders_job

logger = get_logger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler() -> None:
    """
    Inicia o scheduler com jobs configurados.
    
    Jobs:
    - Reminders D-1: todos os dias às 9h (América/São Paulo)
    """
    if scheduler.running:
        logger.warning("Scheduler já está rodando")
        return
    
    tz = ZoneInfo("America/Sao_Paulo")
    
    # Job: Lembretes D-1 às 9h todo dia
    scheduler.add_job(
        _run_reminders_sync,
        CronTrigger(hour=9, minute=0, timezone="America/Sao_Paulo"),
        id="reminders_24h",
        name="Enviar lembretes D-1",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("[OK] Scheduler iniciado com jobs configurados")


def stop_scheduler() -> None:
    """Para o scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("[OK] Scheduler parado")
    else:
        logger.warning("Scheduler não está rodando")


def _run_reminders_sync() -> None:
    """Wrapper sync para job async (APScheduler executa sync)."""
    try:
        asyncio.run(run_reminders_job())
    except Exception as e:
        logger.error(f"Erro ao executar job de reminders: {e}", exc_info=True)


def get_scheduler_info() -> dict:
    """Retorna status do scheduler e jobs ativos."""
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ],
    }


if __name__ == "__main__":
    """
    CLI para testar scheduler.
    
    Uso:
        python -m app.jobs.scheduler
    """
    import time
    
    logger.info("Iniciando scheduler em modo teste...")
    start_scheduler()
    
    try:
        while True:
            info = get_scheduler_info()
            logger.info(f"Scheduler status: {info}")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Encerrando...")
        stop_scheduler()
