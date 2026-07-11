import datetime as dt

from app.models import Cidade, CondicaoAtual, PrevisaoHoraria, SessionLocal
from app.queries import acuracia_previsao, condicao_atual_por_cidade, historico_condicoes


def _popular_cenario_basico():
    agora = dt.datetime.utcnow()
    with SessionLocal() as session:
        cidade = Cidade(nome="São Paulo", latitude=-23.55, longitude=-46.63)
        session.add(cidade)
        session.flush()

        for i in range(3):
            session.add(
                CondicaoAtual(
                    cidade_id=cidade.id,
                    temperatura=20 + i,
                    umidade=60,
                    precipitacao=0,
                    codigo_tempo=1,
                    vento_velocidade=10,
                    coletado_em=agora - dt.timedelta(hours=(3 - i)),
                )
            )
        session.commit()
    return cidade.id


def test_condicao_atual_por_cidade_retorna_ultimo_snapshot():
    _popular_cenario_basico()

    df = condicao_atual_por_cidade()

    assert len(df) == 1
    assert df.iloc[0]["cidade"] == "São Paulo"
    assert df.iloc[0]["temperatura"] == 22  # última das 3 inseridas (20, 21, 22)


def test_historico_condicoes_respeita_janela_de_tempo():
    _popular_cenario_basico()

    df = historico_condicoes(horas=24)
    assert len(df) == 3

    df_curto = historico_condicoes(horas=1)
    assert len(df_curto) <= 1


def test_acuracia_previsao_calcula_erro_medio_por_faixa():
    agora = dt.datetime.utcnow()
    with SessionLocal() as session:
        cidade = Cidade(nome="São Paulo", latitude=-23.55, longitude=-46.63)
        session.add(cidade)
        session.flush()

        hora_alvo = agora  # horário que será "previsto" e depois "observado"

        # Previsão feita 1h antes do horário alvo, com erro de 2 graus
        session.add(
            PrevisaoHoraria(
                cidade_id=cidade.id,
                hora_prevista=hora_alvo,
                temperatura_prevista=25.0,
                coletado_em=hora_alvo - dt.timedelta(hours=1),
            )
        )
        # O que de fato foi observado no horário alvo
        session.add(
            CondicaoAtual(
                cidade_id=cidade.id,
                temperatura=23.0,
                coletado_em=hora_alvo,
            )
        )
        session.commit()

    df = acuracia_previsao(horas=24)

    assert not df.empty
    linha = df.iloc[0]
    assert linha["faixa_antecedencia"] == "≤1h"
    assert linha["erro_medio"] == 2.0
    assert linha["amostras"] == 1


def test_acuracia_previsao_vazia_sem_dados():
    df = acuracia_previsao(horas=24)
    assert df.empty
