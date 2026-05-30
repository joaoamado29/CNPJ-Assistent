"""Persistência do histórico de chat por usuário (tabela chat_messages)."""

from __future__ import annotations

from src.database.models import ChatMessage
from webapp.db import open_session


def carregar_mensagens(user_id: str) -> list[dict]:
    """Retorna o histórico do usuário em ordem cronológica."""
    session = open_session()
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
    session = open_session()
    try:
        session.add(ChatMessage(user_id=user_id, role=role, content=content))
        session.commit()
    finally:
        session.close()


def limpar_mensagens(user_id: str) -> int:
    """Apaga o histórico do usuário e devolve quantas mensagens foram removidas."""
    session = open_session()
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