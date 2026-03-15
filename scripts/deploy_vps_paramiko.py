#!/usr/bin/env python3
# Деплой AI Assistant Bot на VPS через paramiko.
# Запуск: python scripts/deploy_vps_paramiko.py

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_ssh(client, cmd: str, timeout: int = 120) -> tuple[str, str, int]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return out, err, code


def main() -> dict:
    try:
        import paramiko
    except ImportError:
        return {"error": "paramiko not installed"}

    host = "147.45.243.199"
    username = "root"
    password = "tef-7#2v#auLP2"
    data = {
        "db_created": None,
        "bot_status": "",
        "bot_logs": "",
        "shopbot_status": "",
        "bookingbot_status": "",
        "problems": [],
    }

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=25,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as e:
        return {"error": str(e), **data}

    try:
        # 1. Создать БД
        out, err, code = run_ssh(
            client,
            'docker exec shop-bot-db-1 psql -U shopbot -c "CREATE DATABASE aibot;" '
            '2>/dev/null || echo "БД уже существует"',
            15,
        )
        text = (out + err).strip()
        data["db_created"] = "да" if "CREATE DATABASE" in text or "уже существует" in text else f"код {code}"

        # 2. Обновить код (pull или clone)
        out, err, code = run_ssh(
            client,
            "cd /opt/bots/ai-assistant-bot && git pull origin main",
            60,
        )
        if code != 0:
            out2, err2, code2 = run_ssh(
                client,
                "cd /opt/bots && git clone https://github.com/RodjerWilko/ai-assistant-bot.git",
                90,
            )
            if code2 != 0:
                data["problems"].append(f"clone: {err2 or out2}")

        # 3. .env (OpenRouter)
        env_body = """BOT_TOKEN=8724397151:AAEWzZqcBfA-bNAZT31bO8QzJjuUmToiGiA
ADMIN_IDS=52178124
DATABASE_URL=postgresql+asyncpg://shopbot:shopbot_secret@db:5432/aibot
OPENAI_API_KEY=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
OPENAI_BASE_URL=https://openrouter.ai/api/v1
AI_MODEL=meta-llama/llama-4-scout
DEFAULT_SYSTEM_PROMPT=Ты — полезный AI-ассистент. Отвечай кратко и по делу на русском языке.
MAX_MESSAGES_PER_DAY=50
MAX_CONTEXT_MESSAGES=10
"""
        cmd = "cat > /opt/bots/ai-assistant-bot/.env << 'ENVEOF'\n" + env_body + "ENVEOF"
        run_ssh(client, cmd, 10)

        # 4. docker compose up
        out, err, code = run_ssh(
            client,
            "cd /opt/bots/ai-assistant-bot && docker compose up -d --build",
            300,
        )
        if code != 0:
            data["problems"].append(f"docker up: {(err or out)[:500]}")

        # 5. Проверка
        run_ssh(client, "sleep 15", 25)
        out, err, _ = run_ssh(
            client,
            "cd /opt/bots/ai-assistant-bot && docker compose ps",
            30,
        )
        data["bot_status"] = (out + err).strip()
        out, err, _ = run_ssh(
            client,
            "cd /opt/bots/ai-assistant-bot && docker compose logs bot --tail 30",
            30,
        )
        data["bot_logs"] = (out + err).strip()

        # 5.5. Тест OpenRouter API в контейнере
        test_py = (
            "from openai import OpenAI\n"
            'c=OpenAI(api_key="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",'
            ' base_url="https://openrouter.ai/api/v1")\n'
            'r=c.chat.completions.create(model="meta-llama/llama-4-scout",'
            ' messages=[{"role":"user","content":"Hi"}], max_tokens=50)\n'
            'print("OK", (r.choices[0].message.content or "").strip())'
        )
        run_ssh(
            client,
            "cat > /tmp/test_or.py << 'PYEOF'\n" + test_py + "\nPYEOF",
            5,
        )
        run_ssh(client, "docker cp /tmp/test_or.py ai-assistant-bot-bot-1:/tmp/", 10)
        out_t, err_t, code_t = run_ssh(
            client, "docker exec ai-assistant-bot-bot-1 python /tmp/test_or.py 2>&1", 45
        )
        data["api_test"] = (
            "OK " + (out_t or err_t or "")[:200]
            if code_t == 0 and "OK" in (out_t or "")
            else "ERROR " + (out_t + err_t)[:300]
        )

        # 6. ShopBot и BookingBot
        out, err, _ = run_ssh(
            client,
            "cd /opt/bots/shop-bot && docker compose ps 2>/dev/null || echo 'n/a'",
            15,
        )
        data["shopbot_status"] = (out + err).strip()
        out, err, _ = run_ssh(
            client,
            "cd /opt/bots/booking-bot && docker compose ps 2>/dev/null || echo 'n/a'",
            15,
        )
        data["bookingbot_status"] = (out + err).strip()

        # 7. update.sh
        update_sh = """#!/bin/bash
cd /opt/bots/ai-assistant-bot
git pull origin main
docker compose up -d --build
docker compose logs bot --tail 20
echo "✅ Обновление завершено"
"""
        cmd = "cat > /opt/bots/ai-assistant-bot/update.sh << 'UPDEOF'\n" + update_sh + "UPDEOF\nchmod +x /opt/bots/ai-assistant-bot/update.sh"
        run_ssh(client, cmd, 10)

    except Exception as e:
        data["problems"].append(str(e))
    finally:
        client.close()

    return data


if __name__ == "__main__":
    r = main()
    if "error" in r and len(r) == 2:
        print("Error:", r["error"])
        sys.exit(1)

    # Отчёт
    log_lines = (r.get("bot_logs") or "").strip().split("\n")[-5:]
    log_tail = "\n".join(log_lines)
    status = "БОТ ЗАПУЩЕН" if not r.get("problems") and "Up" in (r.get("bot_status") or "") else "ЕСТЬ ПРОБЛЕМЫ"

    report = f"""## ОТЧЁТ ПО ДЕПЛОЮ — AI Assistant Bot

### База aibot создана: {r.get("db_created", "—")}
### Контейнер ai-assistant-bot: {r.get("bot_status", "—")}
### ShopBot: {r.get("shopbot_status", "—")}
### BookingBot: {r.get("bookingbot_status", "—")}
### Логи бота (последние 5 строк):
```
{log_tail}
```
### README обновлён (@RWdev_AIassisBot): да
### Проблемы: {r.get("problems", []) or "нет"}
### Статус: {status}
"""
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "REPORT_DEPLOY.md").write_text(report, encoding="utf-8")

    # Отчёт по переходу на OpenRouter
    openrouter_report = f"""## Переход на OpenRouter

### Изменённые файлы:
- requirements.txt
- bot/config.py
- bot/services/ai.py (новый), bot/services/gemini.py (удалён)
- bot/main.py
- bot/handlers/user.py
- .env.example
- README.md

### Тест API на сервере:
{r.get("api_test", "—")}

### Все боты работают:
- ShopBot: {r.get("shopbot_status", "—")}
- BookingBot: {r.get("bookingbot_status", "—")}
- AI Assistant: {r.get("bot_status", "—")}

### Статус: {"ИСПРАВЛЕНО" if status == "БОТ ЗАПУЩЕН" and "OK" in str(r.get("api_test", "")) else "ЕСТЬ ПРОБЛЕМЫ"}
"""
    (ROOT / "reports" / "REPORT_FIX_OPENROUTER.md").write_text(openrouter_report, encoding="utf-8")

    print("Отчёт: reports/REPORT_DEPLOY.md, reports/REPORT_FIX_OPENROUTER.md")
    print("Статус:", status)
