"""Persistência do histórico de chat por usuário (tabela chat_messages)."""

from __future__ import annotations

import os
from pathlib import Path

from src.database.connection import get_session, init_db
from src.database.models import ChatMessage

_BASE_DIR = Path(__file__).resolve().parent.parent
_initialized = False


def _database_url() -> str:
    """URL do banco do chat. Lê DATABASE_URL do ambiente, sem exigir a config do Telegram."""
    return os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{_BASE_DIR / 'data' / 'agente_telegram.db'}",
    )


def _ensure_db() -> str:
    """Garante que as tabelas existem e devolve a URL do banco."""
    global _initialized
    database_url = _database_url()
    if not _initialized:
        init_db(database_url)
        _initialized = True
    return database_url


def carregar_mensagens(user_id: str) -> list[dict]:
    """Retorna o histórico do usuário em ordem cronológica."""
    database_url = _ensure_db()
    session = get_session(database_url)
    try:
        rows = (
            session.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return [{"role": r.role, "content": r.content} for r in rows]
    finally:
        session.close()


def salvar_mensagem(user_id: str, role: str, content: str) -> None:
    """Grava uma mensagem do usuário ou do assistente."""
    database_url = _ensure_db()
    session = get_session(database_url)
    try:
        session.add(ChatMessage(user_id=user_id, role=role, content=content))
        session.commit()
    finally:
        session.close()


def limpar_mensagens(user_id: str) -> int:
    """Apaga o histórico do usuário e devolve quantas mensagens foram removidas."""
    database_url = _ensure_db()
    session = get_session(database_url)
    try:
        removidas = (
            session.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .delete(synchronize_session=False)
        )
        session.commit()
        return removidas
    finally:
        session.close()
