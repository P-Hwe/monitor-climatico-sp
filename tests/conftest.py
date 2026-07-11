"""
Garante que os testes rodam contra um banco SQLite temporário e isolado,
nunca contra o banco de desenvolvimento/produção.

Precisa definir a variável de ambiente ANTES de qualquer módulo da
aplicação ser importado, pois app/config.py lê DATABASE_URL na importação.
"""
import os
import tempfile

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

import pytest  # noqa: E402

from app.models import Base, engine, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def banco_limpo():
    """Recria as tabelas do zero antes de cada teste."""
    Base.metadata.drop_all(engine)
    init_db()
    yield
