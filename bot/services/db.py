# bot/services/db.py — CRUD для пользователей, диалогов, сообщений
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.models import Conversation, Message, User

logger = logging.getLogger(__name__)


# --- Пользователи ---


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    full_name: str,
) -> User:
    """Получить или создать пользователя."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name or "Пользователь",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    """Пользователь по telegram_id."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def update_system_prompt(
    session: AsyncSession, telegram_id: int, prompt: str
) -> None:
    """Обновить системный промпт пользователя."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.system_prompt = prompt
        await session.commit()


async def reset_system_prompt(session: AsyncSession, telegram_id: int) -> None:
    """Сбросить промпт (None — будет использоваться дефолтный)."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.system_prompt = None
        await session.commit()


async def check_and_increment_limit(
    session: AsyncSession, telegram_id: int, max_per_day: int
) -> bool:
    """
    True если лимит не превышен и счётчик увеличен.
    Если last_message_date != сегодня — сбросить messages_today.
    """
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    today = date.today()
    if user.last_message_date != today:
        user.messages_today = 0
        user.last_message_date = today
    if user.is_premium:
        user.messages_today += 1
        await session.commit()
        return True
    if user.messages_today >= max_per_day:
        return False
    user.messages_today += 1
    user.last_message_date = today
    await session.commit()
    return True


async def get_user_stats(session: AsyncSession, telegram_id: int) -> dict:
    """messages_today, is_premium, system_prompt, created_at."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        return {}
    return {
        "messages_today": user.messages_today,
        "is_premium": user.is_premium,
        "system_prompt": user.system_prompt,
        "created_at": user.created_at,
    }


# --- Диалоги ---


async def get_active_conversation(
    session: AsyncSession, telegram_id: int
) -> Conversation | None:
    """Текущий активный диалог пользователя."""
    result = await session.execute(
        select(Conversation)
        .join(User, User.id == Conversation.user_id)
        .where(User.telegram_id == telegram_id, Conversation.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def create_conversation(
    session: AsyncSession,
    telegram_id: int,
    title: str = "Новый диалог",
) -> Conversation:
    """Создать новый диалог, деактивировать старый."""
    user = await get_user(session, telegram_id)
    if not user:
        user = await get_or_create_user(session, telegram_id, None, "")
    # Деактивировать все текущие
    result = await session.execute(
        select(Conversation).where(Conversation.user_id == user.id)
    )
    for conv in result.scalars().all():
        conv.is_active = False
    new_conv = Conversation(user_id=user.id, title=title, is_active=True)
    session.add(new_conv)
    await session.commit()
    await session.refresh(new_conv)
    return new_conv


async def get_user_conversations(
    session: AsyncSession, telegram_id: int, limit: int = 20
) -> list[Conversation]:
    """Все диалоги пользователя, по дате desc."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return []
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def set_active_conversation(
    session: AsyncSession, telegram_id: int, conversation_id: int
) -> None:
    """Сделать диалог активным, остальные — неактивными."""
    result = await session.execute(
        select(Conversation)
        .join(User, User.id == Conversation.user_id)
        .where(User.telegram_id == telegram_id)
    )
    for conv in result.scalars().all():
        conv.is_active = conv.id == conversation_id
    await session.commit()


# --- Сообщения ---


async def add_message(
    session: AsyncSession,
    conversation_id: int,
    role: str,
    content: str,
    tokens_used: int | None = None,
) -> Message:
    """Добавить сообщение в диалог."""
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tokens_used=tokens_used,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def get_conversation_history(
    session: AsyncSession, conversation_id: int, limit: int
) -> list[Message]:
    """Последние N сообщений для контекста (user/assistant)."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def get_conversation_messages(
    session: AsyncSession, conversation_id: int
) -> list[Message]:
    """Все сообщения диалога по порядку."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


# --- Статистика (админ) ---


async def get_stats(session: AsyncSession) -> dict:
    """users, conversations, messages_total, messages_today, active_users_today."""
    today = date.today()
    users_count = await session.execute(select(func.count(User.id)))
    conv_count = await session.execute(select(func.count(Conversation.id)))
    msg_total = await session.execute(select(func.count(Message.id)))
    # Сообщений сегодня — по created_at сообщений
    msg_today_result = await session.execute(
        select(func.count(Message.id)).where(
            func.date(Message.created_at) == today
        )
    )
    # Активных сегодня — пользователей, у которых есть сообщение сегодня
    active_today = await session.execute(
        select(func.count(func.distinct(Conversation.user_id)))
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(func.date(Message.created_at) == today)
    )
    return {
        "users": users_count.scalar() or 0,
        "conversations": conv_count.scalar() or 0,
        "messages_total": msg_total.scalar() or 0,
        "messages_today": msg_today_result.scalar() or 0,
        "active_users_today": active_today.scalar() or 0,
    }


async def get_recent_users(session: AsyncSession, limit: int = 20) -> list[tuple[User, int]]:
    """Последние пользователи с количеством сообщений (для админки)."""
    result = await session.execute(
        select(User, func.count(Message.id).label("msg_count"))
        .outerjoin(Conversation, Conversation.user_id == User.id)
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    return [(row[0], row[1] or 0) for row in result.all()]
