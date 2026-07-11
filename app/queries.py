"""Funções de consulta ao banco, usadas pelo dashboard (somente leitura)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select

from app.models import Cidade, CondicaoAtual, PrevisaoHoraria, SessionLocal

SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def condicao_atual_por_cidade() -> pd.DataFrame:
    """Última condição observada de cada cidade."""
    with SessionLocal() as session:
        cidades = session.query(Cidade).all()
        registros = []
        for cidade in cidades:
            ultima = (
                session.query(CondicaoAtual)
                .filter_by(cidade_id=cidade.id)
                .order_by(CondicaoAtual.coletado_em.desc())
                .first()
            )
            if ultima is None:
                continue
            registros.append(
                {
                    "cidade": cidade.nome,
                    "temperatura": ultima.temperatura,
                    "sensacao_termica": ultima.sensacao_termica,
                    "umidade": ultima.umidade,
                    "precipitacao": ultima.precipitacao,
                    "codigo_tempo": ultima.codigo_tempo,
                    "vento_velocidade": ultima.vento_velocidade,
                    "coletado_em": ultima.coletado_em,
                }
            )
    df = pd.DataFrame(registros)
    if not df.empty:
        df["coletado_em"] = pd.to_datetime(df["coletado_em"], utc=True).dt.tz_convert(SAO_PAULO_TZ)
    return df


def historico_condicoes(horas: int = 48) -> pd.DataFrame:
    """Série histórica de condições observadas, para gráficos de tendência."""
    limite = dt.datetime.utcnow() - dt.timedelta(hours=horas)
    with SessionLocal() as session:
        stmt = (
            select(
                CondicaoAtual.coletado_em,
                CondicaoAtual.temperatura,
                CondicaoAtual.umidade,
                CondicaoAtual.precipitacao,
                Cidade.nome.label("cidade"),
            )
            .join(Cidade, CondicaoAtual.cidade_id == Cidade.id)
            .where(CondicaoAtual.coletado_em >= limite)
            .order_by(CondicaoAtual.coletado_em)
        )
        df = pd.read_sql(stmt, session.bind)
    if not df.empty:
        df["coletado_em"] = pd.to_datetime(df["coletado_em"], utc=True).dt.tz_convert(SAO_PAULO_TZ)
    return df


def precisao_previsao(horas: int = 24 * 7) -> pd.DataFrame:
    """
    Compara temperatura prevista x observada, agrupando o erro por
    antecedência da previsão (1h, 3h, 6h, 12h, 24h, 48h antes).

    Para cada previsão feita, procura a condição observada mais próxima
    do horário previsto (tolerância de 20 min) e calcula o erro absoluto.
    """
    limite = dt.datetime.utcnow() - dt.timedelta(hours=horas)

    with SessionLocal() as session:
        previsoes = pd.read_sql(
            select(
                PrevisaoHoraria.cidade_id,
                PrevisaoHoraria.hora_prevista,
                PrevisaoHoraria.temperatura_prevista,
                PrevisaoHoraria.coletado_em.label("previsao_feita_em"),
            ).where(PrevisaoHoraria.coletado_em >= limite),
            session.bind,
        )
        condicoes = pd.read_sql(
            select(
                CondicaoAtual.cidade_id,
                CondicaoAtual.coletado_em,
                CondicaoAtual.temperatura.label("temperatura_observada"),
            ).where(CondicaoAtual.coletado_em >= limite),
            session.bind,
        )
        cidades = pd.read_sql(select(Cidade.id, Cidade.nome), session.bind)

    if previsoes.empty or condicoes.empty:
        return pd.DataFrame()

    resultados = []
    tolerancia = pd.Timedelta(minutes=20)

    for cidade_id, grupo_previsoes in previsoes.groupby("cidade_id"):
        grupo_condicoes = condicoes[condicoes["cidade_id"] == cidade_id].sort_values("coletado_em")
        if grupo_condicoes.empty:
            continue

        grupo_previsoes = grupo_previsoes.sort_values("hora_prevista")
        casado = pd.merge_asof(
            grupo_previsoes,
            grupo_condicoes,
            left_on="hora_prevista",
            right_on="coletado_em",
            direction="nearest",
            tolerance=tolerancia,
        ).dropna(subset=["temperatura_observada"])

        casado["cidade_id"] = cidade_id
        resultados.append(casado)

    if not resultados:
        return pd.DataFrame()

    df = pd.concat(resultados, ignore_index=True)
    df = df.merge(cidades, left_on="cidade_id", right_on="id").rename(columns={"nome": "cidade"})

    df["antecedencia_horas"] = (
        (df["hora_prevista"] - df["previsao_feita_em"]).dt.total_seconds() / 3600
    ).round()
    df["erro_absoluto"] = (df["temperatura_prevista"] - df["temperatura_observada"]).abs()

    # Agrupa em faixas de antecedência para leitura mais clara
    faixas = [0, 1, 3, 6, 12, 24, 48, 999]
    rotulos = ["≤1h", "1-3h", "3-6h", "6-12h", "12-24h", "24-48h", "48h+"]
    df["faixa_antecedencia"] = pd.cut(df["antecedencia_horas"], bins=faixas, labels=rotulos)

    resumo = (
        df.groupby("faixa_antecedencia", observed=True)["erro_absoluto"]
        .agg(erro_medio="mean", amostras="count")
        .reset_index()
    )
    resumo["erro_medio"] = resumo["erro_medio"].round(2)
    return resumo
