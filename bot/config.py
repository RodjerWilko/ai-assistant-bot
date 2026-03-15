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
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str = "https://openrouter.ai/api/v1"
    AI_MODEL: str = "meta-llama/llama-4-scout"
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
        openai_key = os.getenv("OPENAI_API_KEY", "")
        openai_base = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        ai_model = os.getenv("AI_MODEL", "meta-llama/llama-4-scout")
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
            OPENAI_API_KEY=openai_key,
            OPENAI_BASE_URL=openai_base,
            AI_MODEL=ai_model,
            DEFAULT_SYSTEM_PROMPT=default_prompt,
            MAX_MESSAGES_PER_DAY=max_per_day,
            MAX_CONTEXT_MESSAGES=max_context,
        )
