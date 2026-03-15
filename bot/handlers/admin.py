# bot/handlers/admin.py — /admin, статистика, пользователи
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.keyboards.kb import admin_menu_kb
from bot.services.db import get_stats, get_recent_users
from bot.utils import edit_safe

router = Router()
_config = Config.from_env()


class AdminFilter:
    """Только пользователи из ADMIN_IDS."""

    def __call__(self, event: Message | CallbackQuery) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        return user.id in _config.ADMIN_IDS


admin_only = AdminFilter()


@router.message(Command("admin"), admin_only)
async def cmd_admin(message: Message) -> None:
    """Админ-панель."""
    text = "🔧 <b>Админ-панель — AI Ассистент</b>"
    await message.answer(text, reply_markup=admin_menu_kb())


@router.callback_query(F.data == "adm:stats", admin_only)
async def cb_adm_stats(callback: CallbackQuery, session) -> None:
    """Статистика."""
    stats = await get_stats(session)
    text = (
        "📊 <b>Статистика AI Ассистента</b>\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"💬 Диалогов: {stats['conversations']}\n"
        f"📝 Сообщений всего: {stats['messages_total']}\n"
        f"📝 Сообщений сегодня: {stats['messages_today']}\n"
        f"🟢 Активных сегодня: {stats['active_users_today']}"
    )
    await edit_safe(callback.message, text, reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:users", admin_only)
async def cb_adm_users(callback: CallbackQuery, session) -> None:
    """Последние 20 пользователей."""
    users_data = await get_recent_users(session, limit=20)
    lines = ["👥 <b>Пользователи:</b>\n"]
    for i, (user, msg_count) in enumerate(users_data, 1):
        name = user.username and f"@{user.username}" or user.full_name or "—"
        reg = user.created_at.strftime("%d.%m.%Y") if user.created_at else "—"
        lines.append(f"{i}. {name} — {msg_count} сообщ., рег. {reg}")
    text = "\n".join(lines)
    await edit_safe(
        callback.message,
        text[:4000],
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()
