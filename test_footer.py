# -*- coding: utf-8 -*-
"""Проверка подвалов с HTML-ссылками в обоих мессенджерах."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

body = "Тест подвала. Проверка ссылок. Можно удалить."
sig = "— Владислав Шапша"

max_footer = '<a href="https://max.ru/klg_alarm">📍Калуга, внимание</a>'
tg_footer = (
    '📌 <a href="https://max.ru/klg_alarm">Подписывайтесь на нас в MAX</a>\n\n'
    '<a href="https://t.me/boost/klg_alarm">Наш канал в MAX</a>'
    '🔴 <a href="https://t.me/boost/klg_alarm">Поддержать канал</a>'
)

# MAX
r = requests.post(
    f"https://platform-api.max.ru/messages?chat_id={os.getenv('MAX_CHAT_ID')}",
    headers={"Authorization": os.getenv("MAX_BOT_TOKEN")},
    json={"text": f"{body}\n\n{sig}\n\n{max_footer}", "format": "html"},
    timeout=30,
)
print("MAX:", r.status_code, r.json())

# Telegram
r = requests.post(
    f"https://api.telegram.org/bot{os.getenv('TG_BOT_TOKEN')}/sendMessage",
    json={
        "chat_id": os.getenv("TG_TARGET_CHANNEL"),
        "text": f"{body}\n\n{sig}\n\n{tg_footer}",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    },
    timeout=30,
)
print("TG:", r.status_code, r.json().get("ok"), r.json().get("description", ""))
