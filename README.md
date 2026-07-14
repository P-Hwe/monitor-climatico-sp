# 🌤️ Monitor Climático 

Pipeline de dados rodando **24/7** que coleta, armazena e visualiza condições climáticas de várias cidades brasileiras, e — como diferencial — acompanha a **acurácia das próprias previsões** ao longo do tempo, comparando o que foi previsto com o que de fato aconteceu depois.

> Projeto pessoal de portfólio, construído com dados abertos da Open-Meteo.

## Por que esse projeto existe

Qualquer dashboard de clima mostra "vai chover hoje?". Este projeto vai um passo além: ele **guarda a própria previsão** a cada coleta e, mais tarde, confronta com o valor observado — permitindo responder "o quão confiável é a previsão feita 1h antes vs. 24h antes?". Essa é uma pergunta de análise de dados de verdade, não só visualização.

Ele demonstra, na prática:
- **ETL automatizado** (extração de API → transformação → carga em banco relacional)
- **Modelagem de dados temporal** (dados observados x dados previstos, com timestamps próprios para cada um)
- **Análise com pandas** (`merge_asof` para casar previsão com observação mais próxima no tempo, agregação por faixa de antecedência)
- **Agendamento e orquestração** (scheduler resiliente a falhas de rede)
- **Consumo de API externa** (tratamento de erros, retry com backoff exponencial)
- **Visualização de dados** (dashboard interativo com séries históricas e métricas de erro)
- **Testes automatizados** (mocks de API, banco isolado, CI no GitHub Actions)
- **Deploy e infraestrutura** (aplicação rodando continuamente em produção)

## Arquitetura

```
┌──────────────────────┐    a cada 30 min      ┌──────────────┐
│   API Open-Meteo      │ ─────────────────────▶│  Coletor     │
│ (clima atual + previ- │                        │ (collector)  │
│  são horária, 5 cida- │                        └──────┬───────┘
│  des)                 │                               │ grava
└──────────────────────┘                               ▼
                                                  ┌──────────────┐
                                                  │  Banco de    │
                                                  │  dados       │
                                                  │ (SQLite/PG)  │
                                                  └──────┬───────┘
                                                         │ lê
                                                         ▼
                                                  ┌──────────────┐
                                                  │  Dashboard   │
                                                  │  (Streamlit) │
                                                  └──────────────┘
```

Em produção, o **scheduler** roda em background dentro do próprio processo do dashboard (`app/scheduler.py`), garantindo que a coleta continue acontecendo mesmo com o serviço rodando como uma única aplicação web — ideal para o tier gratuito de plataformas como Railway ou Render. Também existe um **worker standalone** (`app/worker.py`) para quem preferir separar coleta e visualização em dois serviços.

## Stack

| Camada | Tecnologia |
|---|---|
| Coleta | `requests` + retry/backoff |
| Agendamento | `APScheduler` |
| Banco de dados | `SQLAlchemy` (SQLite local / PostgreSQL em produção) |
| Análise | `pandas` (incluindo `merge_asof` para casar séries temporais) |
| Dashboard | `Streamlit` + `Plotly` |
| Testes | `pytest` + `responses` (mock de HTTP) |
| CI | GitHub Actions |
| Deploy | Railway / Render (free tier) |

## Fonte dos dados

API pública e gratuita **[Open-Meteo](https://open-meteo.com/)**:
`https://api.open-meteo.com/v1/forecast`

- **Sem chave, sem cadastro** — uso imediato
- Gratuita para uso não comercial, até 10.000 chamadas/dia
- Licença de dados CC BY 4.0 (requer atribuição, já incluída no dashboard)
- Modelos meteorológicos de mais de 15 serviços nacionais (ECMWF, NOAA, DWD, entre outros)

Cidades monitoradas por padrão: São Paulo, Guarulhos, Campinas, Rio de Janeiro e Curitiba — configurável em `app/config.py`.

## Rodando localmente

```bash
git clone <seu-repositorio>
cd monitor-climatico-sp

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements-dev.txt

cp .env.example .env  # opcional, não há nada obrigatório para preencher

streamlit run app/dashboard.py
```

O dashboard sobe em `http://localhost:8501` e já dispara a primeira coleta automaticamente. A seção de acurácia de previsão só ganha dados depois de algumas horas de coleta contínua (é preciso que uma previsão "vença" para poder ser comparada com a observação real).

## Rodando os testes

```bash
pytest -v
```

Os testes usam um banco SQLite temporário isolado e **mockam** as chamadas HTTP (biblioteca `responses`) — nenhum teste consome a cota real da API.

## Deploy 24/7 (Railway)

1. Suba o repositório no GitHub.
2. Crie um projeto no [Railway](https://railway.app) e conecte o repositório.
3. Adicione um banco PostgreSQL pelo próprio Railway (`+ New → Database → PostgreSQL`) — a variável `DATABASE_URL` é injetada automaticamente.
4. O `Procfile` já define o comando de start (`web: streamlit run ...`) — o Railway detecta automaticamente.
5. Pronto: o serviço fica no ar continuamente, coletando dados a cada 30 minutos e servindo o dashboard. Sem chave de API para configurar.

> Alternativas: Render (mesmo fluxo) ou uma VM gratuita da Oracle Cloud, rodando `app/worker.py` via `systemd` + o dashboard via `nginx` como proxy reverso — opção mais trabalhosa, mas ótima para aprender administração de infraestrutura de verdade.

## Estrutura do projeto

```
monitor-climatico-sp/
├── app/
│   ├── collector.py      # busca dados na API e grava no banco
│   ├── config.py         # configurações e lista de cidades
│   ├── dashboard.py       # aplicação Streamlit
│   ├── models.py          # schema do banco (SQLAlchemy)
│   ├── queries.py         # consultas de leitura + cálculo de acurácia
│   ├── scheduler.py       # agendador em background
│   ├── weather_codes.py   # tradução dos códigos meteorológicos (WMO)
│   └── worker.py          # processo standalone de coleta
├── tests/
│   ├── conftest.py
│   ├── test_collector.py
│   └── test_queries.py
├── .github/workflows/tests.yml
├── Procfile
├── requirements.txt
└── requirements-dev.txt
```

## Como funciona o cálculo de acurácia

A cada coleta, o sistema grava:
1. A **condição atual** (o que o modelo diz que está acontecendo agora)
2. A **previsão horária** para as próximas 48h (o que o modelo diz que vai acontecer)

Horas depois, quando uma nova coleta registra a condição atual para aquele horário que antes era "futuro", o `queries.acuracia_previsao()` casa cada previsão com a observação mais próxima no tempo (tolerância de 20 min) usando `pandas.merge_asof`, calcula o erro absoluto, e agrupa por faixa de antecedência (≤1h, 1-3h, 3-6h, 6-12h, 12-24h, 24-48h). O resultado normalmente confirma a intuição: previsões de curtíssimo prazo erram menos que previsões de dois dias — mas agora isso é **medido com dados reais**, não assumido.

## Possíveis evoluções

- Alertas via Telegram/e-mail em caso de temperatura extrema ou alta probabilidade de chuva
- Adicionar dados de qualidade do ar (Open-Meteo tem uma API própria para isso)
- Comparar acurácia entre diferentes modelos meteorológicos (ECMWF vs GFS vs ICON)
- Exportar relatórios semanais em PDF

## Licença

MIT — sinta-se à vontade para usar como base para o seu próprio projeto. Dados climáticos sob licença CC BY 4.0 da Open-Meteo.
