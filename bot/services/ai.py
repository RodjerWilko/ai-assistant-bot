# bot/services/ai.py — обёртка над OpenAI-совместимым API (OpenRouter)
from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class AIService:
    """Обёртка над OpenAI-совместимым API (OpenRouter)."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    async def generate_response(
        self,
        user_message: str,
        history: list[dict[str, Any]],
        system_prompt: str = "",
    ) -> str:
        """Отправляет запрос и возвращает ответ. История: [{"role": "user"|"assistant", "content": "..."}]."""
        try:
            messages: list[dict[str, str]] = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            for msg in history:
                content = msg.get("content", msg.get("parts", [""]))
                if isinstance(content, list) and content:
                    content = content[0] if isinstance(content[0], str) else str(content[0])
                messages.append({
                    "role": msg["role"],
                    "content": content,
                })

            messages.append({"role": "user", "content": user_message})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2048,
                temperature=0.7,
            )

            text = response.choices[0].message.content
            return (text or "").strip() or "Пустой ответ от модели."

        except Exception as e:
            logger.exception("Ошибка AI API: %s", e)
            err = str(e).lower()
            if "rate" in err or "429" in err:
                return "⚠️ Лимит запросов к AI исчерпан. Попробуйте через 1–2 минуты."
            return "❌ Не удалось получить ответ. Попробуйте ещё раз."
