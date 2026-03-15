# bot/models/database.py — пул сессий и создание таблиц
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from bot.models import models  # noqa: E402, F401

logger = logging.getLogger(__name__)


def create_session_pool(database_url: str):
    """Создаёт async engine и фабрику сессий."""
    connect_args = {}
    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False
    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
    )
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def create_tables(engine=None, database_url: str | None = None):
    """Создаёт таблицы."""
    from sqlalchemy.ext.asyncio import create_async_engine

    if engine is None and database_url:
        engine = create_async_engine(
            database_url,
            echo=False,
            connect_args=(
                {"check_same_thread": False}
                if "sqlite" in (database_url or "")
                else {}
            ),
        )
    if engine is None:
        raise ValueError("Нужен engine или database_url")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы созданы/проверены.")
