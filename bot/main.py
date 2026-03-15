# bot/main.py — точка входа, конфиг, Gemini, БД, роутеры
from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject

from bot.config import Config
from bot.handlers import admin, user
from bot.middlewares.db import DbSessionMiddleware
from bot.models.database import create_session_pool, create_tables
from bot.services.gemini import GeminiService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


class GeminiMiddleware:
    """Добавляет gemini_service в data для хендлеров."""

    def __init__(self, gemini_service: GeminiService) -> None:
        self.gemini_service = gemini_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["gemini_service"] = self.gemini_service
        return await handler(event, data)


async def main() -> None:
    config = Config.from_env()
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан")
        return
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY не задан")
        return

    session_pool = create_session_pool(config.DATABASE_URL)
    await create_tables(database_url=config.DATABASE_URL)

    gemini_service = GeminiService(config.GEMINI_API_KEY, config.GEMINI_MODEL)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(DbSessionMiddleware(session_pool))
    dp.callback_query.middleware(DbSessionMiddleware(session_pool))
    dp.message.middleware(GeminiMiddleware(gemini_service))
    dp.callback_query.middleware(GeminiMiddleware(gemini_service))

    dp.include_router(admin.router)
    dp.include_router(user.router)

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
