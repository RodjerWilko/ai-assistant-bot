# 🤖 AI Assistant Bot — Telegram-бот с Google Gemini

> Telegram-бот с интеграцией Google Gemini. Задаёте вопрос — получаете ответ. История диалогов, системные промпты, лимиты сообщений, админ-панель. Single-message UI для меню и настроек.

## 🔗 [Бот: @RWdev_AIBot](https://t.me/RWdev_AIBot)

## Возможности

### Для пользователей
- 💬 Диалог с AI на базе Google Gemini
- 📚 Несколько диалогов с историей
- ⚙️ Свой системный промпт (инструкция для AI)
- 📊 Статистика: сообщений в день, лимиты
- 🔄 Новый диалог по команде /new или кнопке

### Для администратора
- 📊 Статистика: пользователи, диалоги, сообщения
- 👥 Список пользователей с количеством сообщений

## Стек

Python 3.11 | aiogram 3.x | Google Gemini API | SQLAlchemy 2.0 (async) | PostgreSQL / SQLite | Docker

## Архитектура

- **Single-message UI** — меню, настройки, список диалогов через редактирование одного сообщения
- Диалог с AI — обычный поток сообщений (вопрос → ответ)
- Обёртка над Gemini API с asyncio.to_thread для асинхронности
- Лимит сообщений в день, контекст последних N сообщений

## Быстрый старт

```bash
git clone https://github.com/RodjerWilko/ai-assistant-bot.git
cd ai-assistant-bot
cp .env.example .env
# Заполните BOT_TOKEN, ADMIN_IDS, GEMINI_API_KEY
pip install -r requirements.txt
python -m bot.main
```

Docker (общий PostgreSQL с другими ботами):

```bash
# Создать БД: docker exec shop-bot-db-1 psql -U shopbot -c "CREATE DATABASE aibot;"
docker compose up -d --build
```

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| BOT_TOKEN | Токен от @BotFather |
| ADMIN_IDS | ID админов через запятую |
| DATABASE_URL | PostgreSQL или sqlite+aiosqlite:///./aibot.db |
| GEMINI_API_KEY | Ключ из Google AI Studio |
| GEMINI_MODEL | Модель (по умолчанию gemini-2.0-flash) |
| DEFAULT_SYSTEM_PROMPT | Системный промпт по умолчанию |
| MAX_MESSAGES_PER_DAY | Лимит сообщений в день (50) |
| MAX_CONTEXT_MESSAGES | Сколько сообщений контекста (10) |

## Структура проекта

```
ai-assistant-bot/
├── bot/
│   ├── main.py
│   ├── config.py
│   ├── utils.py
│   ├── handlers/   (user, admin)
│   ├── models/     (User, Conversation, Message)
│   ├── services/   (db, gemini)
│   ├── keyboards/
│   └── middlewares/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Лицензия

MIT
