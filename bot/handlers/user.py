# bot/handlers/user.py — /start, диалог с AI, настройки, история
from __future__ import annotations

import logging
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.keyboards.kb import (
    back_to_main_kb,
    chat_actions_kb,
    conversations_kb,
    main_menu_kb,
    settings_kb,
)
from bot.services.db import (
    add_message,
    check_and_increment_limit,
    create_conversation,
    get_active_conversation,
    get_conversation_history,
    get_conversation_messages,
    get_or_create_user,
    get_user,
    get_user_conversations,
    get_user_stats,
    set_active_conversation,
    update_system_prompt,
    reset_system_prompt,
)
from bot.utils import delete_safe, edit_safe

logger = logging.getLogger(__name__)
router = Router()
_config = Config.from_env()


class PromptStates(StatesGroup):
    waiting_prompt = State()


# --- /start ---


@router.message(Command("start"))
async def cmd_start(message: Message, session, state: FSMContext) -> None:
    """Приветствие, создание пользователя и первого диалога."""
    await state.clear()
    user = await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name or "",
    )
    conv = await get_active_conversation(session, message.from_user.id)
    if not conv:
        await create_conversation(session, message.from_user.id)
    text = (
        "🤖 <b>AI Ассистент</b>\n\n"
        "Привет! Я — ваш AI-помощник на базе Google Gemini.\n\n"
        "Просто напишите мне вопрос, и я отвечу!\n\n"
        "💡 Подсказки:\n"
        "• Задайте любой вопрос\n"
        "• Я помню контекст диалога\n"
        "• /new — начать новый диалог\n"
        "• /menu — открыть меню"
    )
    await message.answer(text, reply_markup=chat_actions_kb())


# --- Диалог с AI (текстовые сообщения без команд) ---


@router.message(F.text, ~F.text.startswith("/"))
async def handle_user_message(
    message: Message,
    session,
    state: FSMContext,
    gemini_service,
) -> None:
    """Обработка вопроса пользователя — вызов Gemini и ответ."""
    if not message.text or not message.from_user:
        return
    # Проверка лимита
    ok = await check_and_increment_limit(
        session, message.from_user.id, _config.MAX_MESSAGES_PER_DAY
    )
    if not ok:
        await message.answer(
            f"⚠️ Вы достигли лимита {_config.MAX_MESSAGES_PER_DAY} сообщений в день. "
            "Лимит сбросится завтра."
        )
        return
    # Активный диалог
    conv = await get_active_conversation(session, message.from_user.id)
    if not conv:
        conv = await create_conversation(session, message.from_user.id)
    # История до добавления текущего сообщения (для контекста)
    history_raw = await get_conversation_history(
        session, conv.id, _config.MAX_CONTEXT_MESSAGES
    )
    history = [
        {"role": m.role, "parts": [m.content]}
        for m in history_raw
        if m.role in ("user", "assistant")
    ]
    await add_message(session, conv.id, "user", message.text)
    typing_msg = await message.answer("⏳ Думаю...")
    try:
        user = await get_user(session, message.from_user.id)
        system_prompt = (
            user.system_prompt if user and user.system_prompt
            else _config.DEFAULT_SYSTEM_PROMPT
        )
        response = await gemini_service.generate_response(
            message.text, history, system_prompt
        )
    except Exception as e:
        logger.exception("Gemini error: %s", e)
        await delete_safe(message.bot, message.chat.id, typing_msg.message_id)
        await message.answer(
            "❌ Не удалось получить ответ. Попробуйте ещё раз."
        )
        return
    await delete_safe(message.bot, message.chat.id, typing_msg.message_id)
    await add_message(session, conv.id, "assistant", response)
    # Отправка ответа (разбивка при длине >4096)
    chunk_size = 4096
    for i in range(0, len(response), chunk_size):
        chunk = response[i : i + chunk_size]
        try:
            await message.answer(chunk, parse_mode=None)
        except Exception:
            await message.answer(chunk)


# --- Команды и callback ---


@router.message(Command("new"))
@router.message(F.text == "🔄 Новый диалог")
async def cmd_new(message: Message, session, state: FSMContext) -> None:
    """Начать новый диалог."""
    await state.clear()
    await create_conversation(session, message.from_user.id)
    await message.answer(
        "💬 Начат новый диалог. Задавайте вопрос!",
        reply_markup=chat_actions_kb(),
    )


@router.callback_query(F.data == "new_chat")
async def cb_new_chat(callback: CallbackQuery, session, state: FSMContext) -> None:
    await state.clear()
    await create_conversation(session, callback.from_user.id)
    await edit_safe(
        callback.message,
        "💬 Начат новый диалог. Задавайте вопрос!",
    )
    await callback.answer()
    await callback.message.answer("Можете писать сообщения.", reply_markup=chat_actions_kb())


@router.message(Command("menu"))
@router.message(F.text == "📋 Меню")
async def cmd_menu(message: Message, state: FSMContext) -> None:
    """Показать главное меню (новое сообщение с inline)."""
    await state.clear()
    await message.answer("📋 Меню:", reply_markup=main_menu_kb())


@router.callback_query(F.data == "home")
async def cb_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_safe(
        callback.message,
        "📋 <b>Меню</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "my_chats")
async def cb_my_chats(callback: CallbackQuery, session) -> None:
    """Список диалогов пользователя."""
    convs = await get_user_conversations(session, callback.from_user.id)
    text = "📚 <b>Ваши диалоги:</b>"
    if not convs:
        text += "\n\nПока нет диалогов. Нажмите «Новый диалог»."
    await edit_safe(callback.message, text, reply_markup=conversations_kb(convs))
    await callback.answer()


@router.callback_query(F.data.startswith("chat:"))
async def cb_chat(callback: CallbackQuery, session) -> None:
    """Переключиться на диалог и показать последние сообщения."""
    conv_id = int(callback.data.split(":")[1])
    await set_active_conversation(session, callback.from_user.id, conv_id)
    convs = await get_user_conversations(session, callback.from_user.id)
    conv = next((c for c in convs if c.id == conv_id), None)
    if not conv:
        await callback.answer("Диалог не найден", show_alert=True)
        return
    messages = await get_conversation_messages(session, conv_id)
    last_n = messages[-5:] if len(messages) > 5 else messages
    lines = [f"💬 <b>Диалог: {conv.title}</b>\n"]
    for m in last_n:
        prefix = "👤" if m.role == "user" else "🤖"
        lines.append(f"{prefix} {m.content[:200]}{'...' if len(m.content) > 200 else ''}")
    text = "\n\n".join(lines) if lines else "Нет сообщений."
    await edit_safe(
        callback.message,
        text[:4000],
        reply_markup=back_to_main_kb(),
    )
    await callback.answer()
    await callback.message.answer(
        "Переключились на этот диалог. Можете писать сообщения.",
        reply_markup=chat_actions_kb(),
    )


@router.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery) -> None:
    """О боте."""
    text = (
        "ℹ️ <b>AI Ассистент</b>\n\n"
        f"🤖 Модель: Google Gemini\n"
        f"💬 Лимит: {_config.MAX_MESSAGES_PER_DAY} сообщений/день\n"
        f"🧠 Контекст: {_config.MAX_CONTEXT_MESSAGES} сообщений\n\n"
        "Бот помнит контекст текущего диалога.\n"
        "Начните новый диалог через /new."
    )
    await edit_safe(callback.message, text, reply_markup=main_menu_kb())
    await callback.answer()


# --- Настройки ---


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery, session) -> None:
    """Экран настроек."""
    user = await get_user(session, callback.from_user.id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return
    prompt_preview = (
        (user.system_prompt[:150] + "…") if user.system_prompt else "Стандартный"
    )
    text = f"⚙️ <b>Настройки</b>\n\nТекущий системный промпт: {prompt_preview}"
    await edit_safe(callback.message, text, reply_markup=settings_kb(user))
    await callback.answer()


@router.callback_query(F.data == "edit_prompt")
async def cb_edit_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """Ввод системного промпта — FSM."""
    await state.set_state(PromptStates.waiting_prompt)
    await edit_safe(
        callback.message,
        "📝 Отправьте новый системный промпт (инструкцию для AI):",
    )
    await callback.answer()


@router.message(PromptStates.waiting_prompt, F.text)
async def process_prompt_input(
    message: Message, session, state: FSMContext
) -> None:
    """Получение промпта от пользователя."""
    if not message.text:
        return
    await update_system_prompt(session, message.from_user.id, message.text)
    await state.clear()
    await delete_safe(message.bot, message.chat.id, message.message_id)
    await message.answer("✅ Системный промпт обновлён!", reply_markup=main_menu_kb())


@router.callback_query(F.data == "reset_prompt")
async def cb_reset_prompt(callback: CallbackQuery, session) -> None:
    """Сброс промпта на стандартный."""
    await reset_system_prompt(session, callback.from_user.id)
    user = await get_user(session, callback.from_user.id)
    text = "🔄 Промпт сброшен на стандартный."
    await edit_safe(
        callback.message,
        text,
        reply_markup=settings_kb(user) if user else main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "my_stats")
async def cb_my_stats(callback: CallbackQuery, session) -> None:
    """Статистика пользователя."""
    stats = await get_user_stats(session, callback.from_user.id)
    if not stats:
        await callback.answer("Ошибка", show_alert=True)
        return
    created = stats["created_at"].strftime("%d.%m.%Y") if stats.get("created_at") else "—"
    prompt_type = "кастомный" if stats.get("system_prompt") else "стандартный"
    text = (
        "📊 <b>Ваша статистика</b>\n\n"
        f"💬 Сообщений сегодня: {stats['messages_today']} / {_config.MAX_MESSAGES_PER_DAY}\n"
        f"⚙️ Промпт: {prompt_type}\n"
        f"📅 Зарегистрирован: {created}"
    )
    user = await get_user(session, callback.from_user.id)
    await edit_safe(
        callback.message,
        text,
        reply_markup=settings_kb(user) if user else main_menu_kb(),
    )
    await callback.answer()
