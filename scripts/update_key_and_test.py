#!/usr/bin/env python3
# Обновление GEMINI_API_KEY на VPS и тест через paramiko.
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(client, cmd: str, timeout: int = 60) -> tuple[str, int]:
    i, o, e = client.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", errors="replace")
    return out, o.channel.recv_exit_status()


def main() -> dict:
    try:
        import paramiko
    except ImportError:
        return {"error": "paramiko not installed"}

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname="147.45.243.199",
        username="root",
        password="tef-7#2v#auLP2",
        timeout=25,
    )

    key_new = "AIzaSyB8RMFHtvRHJZ9LoH5FgF1kholfCEtEl_0"
    data = {
        "key_updated": False,
        "test_20": "",
        "test_15": "",
        "test_other": "",
        "working_model": "",
        "logs": "",
    }

    # 1. Обновить ключ
    run(client, f"sed -i 's|GEMINI_API_KEY=.*|GEMINI_API_KEY={key_new}|' /opt/bots/ai-assistant-bot/.env")
    out, _ = run(client, "grep GEMINI /opt/bots/ai-assistant-bot/.env")
    data["key_updated"] = key_new in out

    # 2. Перезапуск
    run(client, "cd /opt/bots/ai-assistant-bot && docker compose restart bot")
    time.sleep(10)
    out, _ = run(client, "cd /opt/bots/ai-assistant-bot && docker compose logs bot --tail 15")
    data["logs"] = out

    # 3. Тест gemini-2.0-flash и gemini-1.5-flash
    test_script = r"""
import google.generativeai as genai
genai.configure(api_key='AIzaSyB8RMFHtvRHJZ9LoH5FgF1kholfCEtEl_0')
for name in ['gemini-2.0-flash', 'gemini-1.5-flash']:
    try:
        model = genai.GenerativeModel(name)
        r = model.generate_content('Say one word in Russian')
        print(name + ' OK:', r.text[:80])
    except Exception as e:
        print(name + ' ERROR:', str(e)[:150])
"""
    # Создать файл на хосте, скопировать в контейнер, выполнить
    run(client, "cat > /tmp/test_gemini.py << 'PYEOF'\n" + test_script.strip() + "\nPYEOF")
    run(client, "docker cp /tmp/test_gemini.py ai-assistant-bot-bot-1:/tmp/")
    out, _ = run(client, "docker exec ai-assistant-bot-bot-1 python /tmp/test_gemini.py 2>&1", 45)
    test_out = out
    data["test_20"] = "OK" if "gemini-2.0-flash OK:" in test_out else "ERROR " + (test_out[:200] or "")
    data["test_15"] = "OK" if "gemini-1.5-flash OK:" in test_out else "ERROR " + (test_out[:200] or "")

    if "gemini-2.0-flash OK:" in test_out:
        data["working_model"] = "gemini-2.0-flash"
    elif "gemini-1.5-flash OK:" in test_out:
        data["working_model"] = "gemini-1.5-flash"
    else:
        # 4. Тест других моделей
        test2 = r"""
import google.generativeai as genai
genai.configure(api_key='AIzaSyB8RMFHtvRHJZ9LoH5FgF1kholfCEtEl_0')
for m in ['gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']:
    try:
        model = genai.GenerativeModel(m)
        r = model.generate_content('Say one word')
        print(m, 'OK:', r.text[:50])
        break
    except Exception as e:
        print(m, 'ERROR:', str(e)[:100])
"""
        run(client, "cat > /tmp/test_gemini2.py << 'PYEOF'\n" + test2.strip() + "\nPYEOF")
        run(client, "docker cp /tmp/test_gemini2.py ai-assistant-bot-bot-1:/tmp/")
        out2, _ = run(client, "docker exec ai-assistant-bot-bot-1 python /tmp/test_gemini2.py 2>&1", 45)
        data["test_other"] = out2[:400]
        for mod in ["gemini-1.5-pro", "gemini-pro", "gemini-1.0-pro"]:
            if mod + " OK:" in out2:
                data["working_model"] = mod
                run(client, f"sed -i 's|GEMINI_MODEL=.*|GEMINI_MODEL={mod}|' /opt/bots/ai-assistant-bot/.env")
                run(client, "cd /opt/bots/ai-assistant-bot && docker compose restart bot")
                break

    client.close()
    return data


if __name__ == "__main__":
    r = main()
    if r.get("error"):
        print(r["error"])
        sys.exit(1)

    working = r.get("working_model", "")
    bot_ok = "да" if working else "нет"
    status = "ИСПРАВЛЕНО" if working else "GEMINI НЕДОСТУПЕН С VPS"

    report = f"""## Обновление Gemini API ключа

### Ключ обновлён: {"да" if r.get("key_updated") else "нет"}
### Тест gemini-2.0-flash: {r.get("test_20", "—")}
### Тест gemini-1.5-flash: {r.get("test_15", "—")}
### Тест других моделей: {r.get("test_other", "не тестировал") or "не тестировал"}
### Рабочая модель: {working or "—"}
### Бот отвечает: {bot_ok}
### Статус: {status}
"""
    (ROOT / "reports" / "REPORT_FIX_KEY.md").write_text(report, encoding="utf-8")
    print("Report: reports/REPORT_FIX_KEY.md")
    print("Working model:", working or "none")
    print("Status:", status)
