from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from typing import List

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class ConsultaRequest(Base):
    __tablename__ = "consulta_requests"
    """Uma consulta (com N CNPJs) feita por um usuário logado na web."""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    total_cnpjs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_cnpjs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    queries: Mapped[List["CNPJQuery"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )

class CNPJQuery(Base):
    __tablename__ = "cnpj_queries"
    """Stores the result of a single CNPJ lookup against the Simples Nacional portal."""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    request_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("consulta_requests.id"), nullable=False, index=True
    )
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, index=True)
    nome_empresarial: Mapped[str | None] = mapped_column(String(500), nullable=True)
    situacao_simples: Mapped[str | None] = mapped_column(String(500), nullable=True)
    situacao_simei: Mapped[str | None] = mapped_column(String(500), nullable=True)
    periodos_anteriores_sn: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    periodos_anteriores_simei: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    eventos_futuros_sn: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    eventos_futuros_simei: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    mei_transportador_autonomo_cargas: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped["ConsultaRequest"] = relationship(
        back_populates="queries"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    """Histórico de mensagens do chat, por usuário logado."""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)