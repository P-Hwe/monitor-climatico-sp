import responses

from app.collector import coletar_clima
from app.config import API_BASE_URL, CIDADES
from app.models import Cidade, CondicaoAtual, PrevisaoHoraria, SessionLocal

PAYLOAD_EXEMPLO = {
    "latitude": -23.55,
    "longitude": -46.63,
    "current": {
        "time": "2026-07-01T10:00",
        "temperature_2m": 22.5,
        "relative_humidity_2m": 68,
        "apparent_temperature": 21.8,
        "precipitation": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 12.3,
        "pressure_msl": 1015.2,
        "cloud_cover": 40,
    },
    "hourly": {
        "time": [
            "2026-07-01T11:00",
            "2026-07-01T12:00",
            "2026-07-01T13:00",
        ],
        "temperature_2m": [23.0, 24.1, 24.8],
        "precipitation_probability": [10, 15, 20],
        "weather_code": [1, 2, 3],
    },
}


def _mockar_todas_as_cidades():
    # Registra uma resposta idêntica para cada cidade configurada
    # (o coletor faz uma chamada por cidade).
    for _ in CIDADES:
        responses.add(responses.GET, API_BASE_URL, json=PAYLOAD_EXEMPLO, status=200)


@responses.activate
def test_coletar_clima_grava_condicao_e_previsao_por_cidade():
    _mockar_todas_as_cidades()

    resumo = coletar_clima()

    assert resumo["cidades"] == len(CIDADES)
    assert resumo["condicoes"] == len(CIDADES)
    assert resumo["previsoes"] == len(CIDADES) * 3  # 3 horas de previsão no payload

    with SessionLocal() as session:
        assert session.query(Cidade).count() == len(CIDADES)
        assert session.query(CondicaoAtual).count() == len(CIDADES)
        assert session.query(PrevisaoHoraria).count() == len(CIDADES) * 3

        condicao = session.query(CondicaoAtual).first()
        assert condicao.temperatura == 22.5
        assert condicao.codigo_tempo == 2


@responses.activate
def test_coletar_clima_nao_duplica_cidade_entre_ciclos():
    _mockar_todas_as_cidades()
    coletar_clima()
    _mockar_todas_as_cidades()
    coletar_clima()

    with SessionLocal() as session:
        assert session.query(Cidade).count() == len(CIDADES)
        # cada ciclo adiciona uma nova condição por cidade
        assert session.query(CondicaoAtual).count() == len(CIDADES) * 2


@responses.activate
def test_coletar_clima_continua_mesmo_se_uma_cidade_falhar(monkeypatch):
    # Primeira cidade falha 3x (esgota as tentativas), as demais funcionam
    responses.add(responses.GET, API_BASE_URL, status=500)
    responses.add(responses.GET, API_BASE_URL, status=500)
    responses.add(responses.GET, API_BASE_URL, status=500)
    for _ in CIDADES[1:]:
        responses.add(responses.GET, API_BASE_URL, json=PAYLOAD_EXEMPLO, status=200)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    resumo = coletar_clima()

    assert resumo["cidades"] == len(CIDADES) - 1
