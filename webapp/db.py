"""Plumbing compartilhado de banco para a camada web."""

from __future__ import annotations

import os
from pathlib import Path

from src.database.connection import get_session, init_db
from src.database.repository import Repository

_BASE_DIR = Path(__file__).resolve().parent.parent
_initialized = False
_repo: Repository | None = None


def database_url() -> str:
    """URL do banco. Lê DATABASE_URL do ambiente, com fallback pro SQLite local."""
    return os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{_BASE_DIR / 'data' / 'consulta_cnpj.db'}",
    )


def _ensure() -> str:
    global _initialized
    url = database_url()
    if not _initialized:
        init_db(url)
        _initialized = True
    return url


def open_session():
    """Sessão SQLAlchemy. Lembre de fechar (try/finally)."""
    return get_session(_ensure())


def repo() -> Repository:
    """Repository singleton da camada web."""
    global _repo
    url = _ensure()
    if _repo is None:
        _repo = Repository(url)
    return _repo