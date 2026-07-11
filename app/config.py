"""Configurações da aplicação, lidas de variáveis de ambiente (.env)."""
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///monitor_climatico.db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

# API Open-Meteo: gratuita, sem chave, até 10.000 chamadas/dia (uso não comercial).
API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SEGUNDOS = 15
USER_AGENT = "monitor-climatico-sp/1.0 (projeto de portfolio; github.com/seu-usuario)"

# Clima muda devagar comparado a status de transporte; 30 min é mais que suficiente
# e mantém o consumo de API bem abaixo do limite diário.
COLETA_INTERVALO_MINUTOS = int(os.getenv("COLETA_INTERVALO_MINUTOS", "30"))

# Cidades monitoradas. Adicione/remova livremente — cada uma vira uma linha
# separada no banco e uma série própria no dashboard.
CIDADES = [
    {"nome": "São Paulo", "latitude": -23.5505, "longitude": -46.6333},
    {"nome": "Guarulhos", "latitude": -23.4543, "longitude": -46.5337},
    {"nome": "Campinas", "latitude": -22.9099, "longitude": -47.0626},
    {"nome": "Rio de Janeiro", "latitude": -22.9068, "longitude": -43.1729},
    {"nome": "Curitiba", "latitude": -25.4284, "longitude": -49.2733},
]

# Até quantas horas à frente guardamos de previsão horária a cada coleta
# (usado depois para calcular o erro de previsão por antecedência).
HORIZONTE_PREVISAO_HORAS = 48
