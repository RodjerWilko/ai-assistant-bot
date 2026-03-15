# bot/config.py — конфигурация из .env
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Конфигурация бота. Загрузка из переменных окружения."""

    BOT_TOKEN: str
    ADMIN_IDS: list[int]
    DATABASE_URL: str
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    DEFAULT_SYSTEM_PROMPT: str = (
        "Ты — полезный AI-ассистент. Отвечай кратко и по делу на русском языке."
    )
    MAX_MESSAGES_PER_DAY: int = 50
    MAX_CONTEXT_MESSAGES: int = 10

    @classmethod
    def from_env(cls) -> Config:
        token = os.getenv("BOT_TOKEN", "")
        admin_raw = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_raw.split(",") if x.strip()]
        db_url = os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./aibot.db",
        )
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        default_prompt = os.getenv(
            "DEFAULT_SYSTEM_PROMPT",
            "Ты — полезный AI-ассистент. Отвечай кратко и по делу на русском языке.",
        )
        max_per_day = int(os.getenv("MAX_MESSAGES_PER_DAY", "50"))
        max_context = int(os.getenv("MAX_CONTEXT_MESSAGES", "10"))
        return cls(
            BOT_TOKEN=token,
            ADMIN_IDS=admin_ids,
            DATABASE_URL=db_url,
            GEMINI_API_KEY=gemini_key,
            GEMINI_MODEL=gemini_model,
            DEFAULT_SYSTEM_PROMPT=default_prompt,
            MAX_MESSAGES_PER_DAY=max_per_day,
            MAX_CONTEXT_MESSAGES=max_context,
        )
