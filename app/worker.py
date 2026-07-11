"""
Worker standalone: fica coletando dados 24/7 em loop, sem subir o dashboard.

Uso:
    python -m app.worker
"""
from __future__ import annotations

import logging
import time

from app.collector import coletar_clima
from app.config import COLETA_INTERVALO_MINUTOS

logger = logging.getLogger("monitor_climatico.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("Worker iniciado. Coletando a cada %s minuto(s).", COLETA_INTERVALO_MINUTOS)

    while True:
        inicio = time.monotonic()
        try:
            coletar_clima()
        except Exception:
            logger.exception("Erro durante o ciclo de coleta. Seguindo para o próximo ciclo.")

        duracao = time.monotonic() - inicio
        espera = max(0, COLETA_INTERVALO_MINUTOS * 60 - duracao)
        time.sleep(espera)


if __name__ == "__main__":
    main()
