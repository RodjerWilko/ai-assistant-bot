# bot/services/gemini.py — обёртка над Google Gemini API
from __future__ import annotations

import asyncio
import logging
from typing import Any

import google.generativeai as genai

try:
    from google.api_core.exceptions import ResourceExhausted
except ImportError:
    ResourceExhausted = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)
QUOTA_EXCEEDED_MSG = (
    "⚠️ Лимит запросов к AI исчерпан. Попробуйте через 1–2 минуты."
)

# Максимальная длина ответа в символах (ориентир для разбивки)
MAX_RESPONSE_LEN = 4000


class GeminiService:
    """Обёртка над Google Gemini API. Синхронные вызовы выполняются в thread."""

    def __init__(self, api_key: str, model_name: str) -> None:
        genai.configure(api_key=api_key)
        self.model_name = model_name

    def _generate_sync(
        self,
        user_message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
    ) -> str:
        """
        Синхронный вызов Gemini. history: [{"role": "user"|"model", "parts": ["текст"]}].
        При 429 (квота) — пробуем fallback-модель gemini-1.5-flash, иначе возвращаем сообщение.
        """
        def _call(model_name: str) -> str:
            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_prompt or "Ты полезный ассистент.",
            )
            gemini_history = []
            for h in history:
                role = "user" if h["role"] == "user" else "model"
                parts = h.get("parts", [h.get("content", "")])
                if isinstance(parts, list) and parts:
                    text = (
                        parts[0]
                        if isinstance(parts[0], str)
                        else parts[0].get("text", "")
                    )
                else:
                    text = str(parts)
                gemini_history.append({"role": role, "parts": [text]})
            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(user_message)
            if not response or not response.text:
                return "Пустой ответ от модели."
            return response.text.strip()

        try:
            return _call(self.model_name)
        except Exception as e:
            if ResourceExhausted and isinstance(e, ResourceExhausted):
                logger.warning("Gemini quota exceeded (429), trying fallback model")
                if self.model_name == "gemini-2.0-flash":
                    try:
                        return _call("gemini-1.5-flash")
                    except Exception:
                        pass
                return QUOTA_EXCEEDED_MSG
            logger.exception("Gemini API error: %s", e)
            raise

    async def generate_response(
        self,
        user_message: str,
        history: list[dict[str, Any]],
        system_prompt: str = "",
    ) -> str:
        """
        Асинхронно отправляет запрос в Gemini и возвращает ответ.
        Синхронная библиотека вызывается через asyncio.to_thread.
        """
        try:
            return await asyncio.to_thread(
                self._generate_sync,
                user_message,
                history,
                system_prompt or "Ты — полезный AI-ассистент. Отвечай кратко на русском.",
            )
        except Exception as e:
            logger.exception("generate_response: %s", e)
            raise
