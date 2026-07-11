"""
Coletor de dados: para cada cidade configurada, busca o clima atual e a
previsão horária na API Open-Meteo, e grava tudo no banco.

Resiliente a falhas de rede (retry com backoff) e não depende de API key.
"""
from __future__ import annotations

import datetime as dt
import logging
import time

import requests

from app.config import (
    API_BASE_URL,
    CIDADES,
    HORIZONTE_PREVISAO_HORAS,
    REQUEST_TIMEOUT_SEGUNDOS,
    USER_AGENT,
)
from app.models import Cidade, CondicaoAtual, PrevisaoHoraria, SessionLocal, init_db

logger = logging.getLogger("monitor_climatico.collector")

VARS_ATUAL = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "pressure_msl",
    "cloud_cover",
]
VARS_HORARIA = ["temperature_2m", "precipitation_probability", "weather_code"]


def _get_or_create_cidade(session, dados_cidade: dict) -> Cidade:
    cidade = session.query(Cidade).filter_by(nome=dados_cidade["nome"]).one_or_none()
    if cidade is None:
        cidade = Cidade(
            nome=dados_cidade["nome"],
            latitude=dados_cidade["latitude"],
            longitude=dados_cidade["longitude"],
        )
        session.add(cidade)
        session.flush()
    return cidade


def _fetch_clima(latitude: float, longitude: float, max_tentativas: int = 3) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(VARS_ATUAL),
        "hourly": ",".join(VARS_HORARIA),
        "forecast_days": max(1, -(-HORIZONTE_PREVISAO_HORAS // 24)),  # arredonda p/ cima
        "timezone": "America/Sao_Paulo",
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    ultimo_erro: Exception | None = None
    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = requests.get(
                API_BASE_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SEGUNDOS
            )

            if resp.status_code == 429:
                espera = int(resp.headers.get("Retry-After", 60))
                logger.warning("Rate limit atingido. Aguardando %ss.", espera)
                time.sleep(espera)
                continue

            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as exc:
            ultimo_erro = exc
            espera = 2**tentativa
            logger.warning(
                "Falha ao consultar API (tentativa %s/%s): %s. Retentando em %ss.",
                tentativa,
                max_tentativas,
                exc,
                espera,
            )
            time.sleep(espera)

    raise RuntimeError(
        f"Não foi possível obter dados da API após {max_tentativas} tentativas"
    ) from ultimo_erro


def _gravar_condicao_atual(session, cidade: Cidade, dados: dict) -> None:
    atual = dados.get("current", {})
    session.add(
        CondicaoAtual(
            cidade_id=cidade.id,
            temperatura=atual["temperature_2m"],
            sensacao_termica=atual.get("apparent_temperature"),
            umidade=atual.get("relative_humidity_2m"),
            precipitacao=atual.get("precipitation"),
            codigo_tempo=atual.get("weather_code"),
            vento_velocidade=atual.get("wind_speed_10m"),
            pressao=atual.get("pressure_msl"),
            nebulosidade=atual.get("cloud_cover"),
            coletado_em=dt.datetime.utcnow(),
        )
    )


def _gravar_previsao_horaria(session, cidade: Cidade, dados: dict) -> int:
    horaria = dados.get("hourly", {})
    horarios = horaria.get("time", [])[:HORIZONTE_PREVISAO_HORAS]
    temperaturas = horaria.get("temperature_2m", [])
    probabilidades = horaria.get("precipitation_probability", [])
    codigos = horaria.get("weather_code", [])

    agora = dt.datetime.utcnow()
    total = 0
    for i, horario_str in enumerate(horarios):
        session.add(
            PrevisaoHoraria(
                cidade_id=cidade.id,
                hora_prevista=dt.datetime.fromisoformat(horario_str),
                temperatura_prevista=temperaturas[i],
                probabilidade_precipitacao=probabilidades[i] if i < len(probabilidades) else None,
                codigo_tempo_previsto=codigos[i] if i < len(codigos) else None,
                coletado_em=agora,
            )
        )
        total += 1
    return total


def coletar_clima() -> dict:
    """Executa um ciclo de coleta para todas as cidades configuradas."""
    init_db()

    resumo = {"cidades": 0, "condicoes": 0, "previsoes": 0}
    with SessionLocal() as session:
        for dados_cidade in CIDADES:
            try:
                dados = _fetch_clima(dados_cidade["latitude"], dados_cidade["longitude"])
            except RuntimeError:
                logger.exception("Falha ao coletar clima de %s. Pulando.", dados_cidade["nome"])
                continue

            cidade = _get_or_create_cidade(session, dados_cidade)
            _gravar_condicao_atual(session, cidade, dados)
            total_previsoes = _gravar_previsao_horaria(session, cidade, dados)

            resumo["cidades"] += 1
            resumo["condicoes"] += 1
            resumo["previsoes"] += total_previsoes

        session.commit()

    logger.info(
        "Coleta concluída: %s cidade(s), %s condição(ões) atual(is), %s previsão(ões).",
        resumo["cidades"],
        resumo["condicoes"],
        resumo["previsoes"],
    )
    return resumo


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    coletar_clima()
