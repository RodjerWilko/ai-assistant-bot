# bot/keyboards/kb.py — клавиатуры (inline + reply)
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.models.models import Conversation, User


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню: Новый диалог | Мои диалоги | Настройки | О боте."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Новый диалог", callback_data="new_chat")],
        [InlineKeyboardButton(text="📚 Мои диалоги", callback_data="my_chats")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")],
    ])


def conversations_kb(conversations: list[Conversation]) -> InlineKeyboardMarkup:
    """Список диалогов. Кнопка: 💬 {title} ({дата}). Внизу Главная."""
    rows = [
        [InlineKeyboardButton(
            text=f"💬 {c.title} ({c.created_at.strftime('%d.%m.%Y')})",
            callback_data=f"chat:{c.id}",
        )]
        for c in conversations
    ]
    rows.append([InlineKeyboardButton(text="🏠 Главная", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(user: User) -> InlineKeyboardMarkup:
    """Настройки: Системный промпт | Сбросить | Статистика | Главная."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Системный промпт", callback_data="edit_prompt")],
        [InlineKeyboardButton(text="🔄 Сбросить промпт", callback_data="reset_prompt")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="home")],
    ])


def chat_actions_kb() -> ReplyKeyboardMarkup:
    """Reply-клавиатура в диалоге: Новый диалог | Меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Новый диалог"),
                KeyboardButton(text="📋 Меню"),
            ],
        ],
        resize_keyboard=True,
    )


def back_to_main_kb() -> InlineKeyboardMarkup:
    """Одна кнопка — Главная (для просмотра диалога)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главная", callback_data="home")],
    ])


def admin_menu_kb() -> InlineKeyboardMarkup:
    """Админ: Статистика | Пользователи | Главная."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="home")],
    ])
