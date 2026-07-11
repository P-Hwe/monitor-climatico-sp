"""Agendador em background: roda o coletor a cada N minutos (padrão: 30)."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.collector import coletar_clima
from app.config import COLETA_INTERVALO_MINUTOS

logger = logging.getLogger("monitor_climatico.scheduler")


def _job_com_tratamento_de_erro():
    try:
        coletar_clima()
    except Exception:
        logger.exception("Erro durante o ciclo de coleta.")


def iniciar_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        _job_com_tratamento_de_erro,
        trigger=IntervalTrigger(minutes=COLETA_INTERVALO_MINUTOS),
        id="coleta_clima",
        next_run_time=None,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado: coleta a cada %s minuto(s).", COLETA_INTERVALO_MINUTOS)
    return scheduler
