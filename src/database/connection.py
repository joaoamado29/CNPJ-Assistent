from __future__ import annotations

import logging
import os
from pathlib import Path

# Before libpq/psycopg run: reduces encoding mismatches on Windows (CP1252 vs UTF-8).
os.environ.setdefault("PGCLIENTENCODING", "UTF8")

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _sqlalchemy_url_for_driver(database_url: str) -> str:
    """Use psycopg3 for PostgreSQL so error messages and Unicode work reliably on Windows."""
    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://") :]
    return database_url


def get_engine(database_url: str) -> Engine:
    global _engine
    if _engine is None:
        url = _sqlalchemy_url_for_driver(database_url)
        if database_url.startswith("sqlite"):
            db_path = database_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        _engine = create_engine(
            url,
            echo=False,
            pool_pre_ping=True,
        )
        logger.info("Database engine created: %s", url.split("@")[-1])
    return _engine


def get_session(database_url: str) -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal()


def init_db(database_url: str) -> None:
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    _ensure_cnpj_queries_columns(engine)
    logger.info("Database tables created/verified.")


def _ensure_cnpj_queries_columns(engine: Engine) -> None:
    """Lightweight schema migration for added result columns.

    `create_all()` does not alter existing tables. We ensure new columns exist so
    older databases keep working without manual migrations.
    """
    desired_columns: dict[str, str] = {
        "periodos_anteriores_sn": "TEXT",
        "periodos_anteriores_simei": "TEXT",
        "eventos_futuros_sn": "TEXT",
        "eventos_futuros_simei": "TEXT",
        "mei_transportador_autonomo_cargas": "TEXT",
    }

    dialect = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dialect == "sqlite":
                existing = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info('cnpj_queries')")).fetchall()
                }
                for col, col_type in desired_columns.items():
                    if col not in existing:
                        conn.execute(
                            text(f"ALTER TABLE cnpj_queries ADD COLUMN {col} {col_type}")
                        )
            elif dialect.startswith("postgresql"):
                existing = {
                    row[0]
                    for row in conn.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'cnpj_queries'"
                        )
                    ).fetchall()
                }
                for col, col_type in desired_columns.items():
                    if col not in existing:
                        conn.execute(
                            text(f"ALTER TABLE public.cnpj_queries ADD COLUMN {col} {col_type}")
                        )
            else:
                # Other DBs: skip silently.
                return
    except Exception as exc:
        # Non-fatal: if migration fails, the app may still run on fresh DBs.
        logger.warning("Could not ensure new columns in cnpj_queries: %s", exc)
