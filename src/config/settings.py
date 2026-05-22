from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Por padrão lê o .env da raiz do projeto. Sobrescreva com a env var ENV_FILE se quiser outro caminho.
ENV_FILE = Path(os.environ.get("ENV_FILE", str(BASE_DIR / ".env")))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    telegram_bot_token: str
    telegram_allowed_users: list[int] = []

    # --- Database ---
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'agente_telegram.db'}"

    # --- Automation ---
    chrome_headless: bool = True
    max_workers: int = 1
    request_delay_seconds: float = 2.0
    max_retries: int = 3
    request_timeout_seconds: int = 60
    page_load_timeout_seconds: int = 30

    # --- Export ---
    export_dir: str = str(BASE_DIR / "exports")

    # --- Logging ---
    log_level: str = "INFO"
    log_file: str = str(BASE_DIR / "logs" / "agente_telegram.log")

    @field_validator("telegram_allowed_users", mode="before")
    @classmethod
    def parse_allowed_users(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(uid.strip()) for uid in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
