"""
Dashboard do Monitor Climático SP.

Rodar localmente:
    streamlit run app/dashboard.py

Este processo também sobe o scheduler em background (thread), então
enquanto o dashboard estiver de pé, a coleta continua rodando a cada
30 minutos — é isso que garante o funcionamento 24/7 em produção.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import plotly.express as px
import streamlit as st

from app.collector import coletar_clima
from app.queries import precisao_previsao as precisao_previsao, condicao_atual_por_cidade, historico_condicoes
from app.scheduler import iniciar_scheduler
from app.weather_codes import descrever_codigo_tempo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

st.set_page_config(page_title="Monitor Climático SP", page_icon="🌤️", layout="wide")


@st.cache_resource
def _bootstrap():
    """Garante que existe pelo menos uma coleta e liga o scheduler (uma única vez)."""
    try:
        coletar_clima()
    except Exception as exc:
        logging.warning("Primeira coleta falhou: %s", exc)
    return iniciar_scheduler()


_bootstrap()

st.title("🌤️ Monitor Climático SP")
st.caption(
    "Clima em tempo real de várias cidades — dados da API pública Open-Meteo, "
    "coletados automaticamente a cada 30 minutos, com acompanhamento da precisão das previsões."
)

df_atual = condicao_atual_por_cidade()

if df_atual.empty:
    st.info("Ainda não há dados coletados. Aguarde o primeiro ciclo de coleta (poucos segundos).")
    st.stop()

# ---------- Condições atuais ----------
st.subheader("Condições atuais")

cols = st.columns(len(df_atual))
for col, (_, cidade) in zip(cols, df_atual.iterrows()):
    with col:
        st.metric(cidade["cidade"], f"{cidade['temperatura']:.1f}°C")
        st.caption(descrever_codigo_tempo(cidade["codigo_tempo"]))
        st.caption(f"💧 {cidade['umidade']:.0f}% · 🌬️ {cidade['vento_velocidade']:.0f} km/h")

st.divider()

# ---------- Tendências ----------
st.subheader("Tendências")

periodo = st.selectbox("Período", ["Últimas 24 horas", "Últimas 48 horas", "Últimos 7 dias"], index=0)
horas = {"Últimas 24 horas": 24, "Últimas 48 horas": 48, "Últimos 7 dias": 24 * 7}[periodo]

df_hist = historico_condicoes(horas)
if not df_hist.empty:
    df_hist = df_hist.sort_values(["cidade", "coletado_em"])

tab_temp, tab_precip = st.tabs(["Temperatura", "Precipitação"])

with tab_temp:
    if df_hist.empty:
        st.info("Ainda não há histórico suficiente para este período.")
    else:
        fig = px.line(
            df_hist,
            x="coletado_em",
            y="temperatura",
            color="cidade",
            markers=True,
            labels={"coletado_em": "", "temperatura": "Temperatura (°C)"},
            title=f"Temperatura por cidade — {periodo.lower()}",
        )
        fig.update_traces(line=dict(width=2), marker=dict(size=6))
        st.plotly_chart(fig, use_container_width=True)

        if df_hist.groupby("cidade").size().max() < 2:
            st.caption("As linhas aparecem depois que houver pelo menos duas coletas por cidade.")

with tab_precip:
    if df_hist.empty:
        st.info("Ainda não há histórico suficiente para este período.")
    else:
        fig = px.bar(
            df_hist,
            x="coletado_em",
            y="precipitacao",
            color="cidade",
            barmode="group",
            labels={"coletado_em": "", "precipitacao": "Precipitação (mm)"},
            title=f"Precipitação por cidade — {periodo.lower()}",
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------- Precisão das previsões ----------
st.subheader("Precisão das previsões")
st.caption(
    "Compara a temperatura prevista com a que de fato foi observada depois, "
    "agrupada pela antecedência com que a previsão foi feita. Quanto mais dados "
    "acumularem ao longo do tempo, mais confiável fica essa análise."
)

df_previsao = precisao_previsao(24 * 7)

if df_previsao.empty:
    st.info(
        "Ainda não há pares de previsão/observação suficientes para calcular a precisão. "
        "Isso aparece naturalmente depois de algumas horas de coleta contínua."
    )
else:
    fig = px.bar(
        df_previsao,
        x="faixa_antecedencia",
        y="erro_medio",
        text="amostras",
        labels={"faixa_antecedencia": "Antecedência da previsão", "erro_medio": "Erro médio (°C)"},
        title="Erro médio de temperatura por antecedência da previsão",
    )
    fig.update_traces(texttemplate="n=%{text}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(
    "Fonte dos dados: Open-Meteo (open-meteo.com), API gratuita para uso não comercial. "
    "Projeto pessoal de portfólio."
)
