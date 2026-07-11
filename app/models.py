"""
Modelos de dados para o Monitor Climático SP.

Schema:
    Cidade            -> cada local monitorado
    CondicaoAtual     -> snapshot do clima observado num instante
    PrevisaoHoraria   -> previsão feita numa coleta para uma hora futura
                         (permite depois comparar previsto x observado)
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Cidade(Base):
    __tablename__ = "cidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    condicoes: Mapped[list["CondicaoAtual"]] = relationship(back_populates="cidade")
    previsoes: Mapped[list["PrevisaoHoraria"]] = relationship(back_populates="cidade")


class CondicaoAtual(Base):
    """O clima observado (segundo o modelo) no momento da coleta."""

    __tablename__ = "condicoes_atuais"

    id: Mapped[int] = mapped_column(primary_key=True)
    cidade_id: Mapped[int] = mapped_column(ForeignKey("cidades.id"), index=True)

    temperatura: Mapped[float] = mapped_column(Float)
    sensacao_termica: Mapped[float | None] = mapped_column(Float, nullable=True)
    umidade: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitacao: Mapped[float | None] = mapped_column(Float, nullable=True)
    codigo_tempo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vento_velocidade: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressao: Mapped[float | None] = mapped_column(Float, nullable=True)
    nebulosidade: Mapped[float | None] = mapped_column(Float, nullable=True)

    coletado_em: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, index=True
    )

    cidade: Mapped["Cidade"] = relationship(back_populates="condicoes")


class PrevisaoHoraria(Base):
    """
    Uma previsão feita numa coleta para uma hora específica no futuro.

    Guardar isso ao longo do tempo permite, depois, comparar a previsão
    feita X horas antes com o que foi de fato observado (CondicaoAtual)
    naquele horário — ou seja, medir a acurácia do modelo climático.
    """

    __tablename__ = "previsoes_horarias"

    id: Mapped[int] = mapped_column(primary_key=True)
    cidade_id: Mapped[int] = mapped_column(ForeignKey("cidades.id"), index=True)

    hora_prevista: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    temperatura_prevista: Mapped[float] = mapped_column(Float)
    probabilidade_precipitacao: Mapped[float | None] = mapped_column(Float, nullable=True)
    codigo_tempo_previsto: Mapped[int | None] = mapped_column(Integer, nullable=True)

    coletado_em: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, index=True
    )

    cidade: Mapped["Cidade"] = relationship(back_populates="previsoes")


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
