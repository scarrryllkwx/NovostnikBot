# -*- coding: utf-8 -*-
"""Разовая проверка: может ли Telegram-бот публиковать в целевой канал."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TG_BOT_TOKEN")
channel = os.getenv("TG_TARGET_CHANNEL")

r = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={"chat_id": channel, "text": "Тестовое сообщение: проверка прав бота. Можно удалить."},
    timeout=30,
)
print(r.status_code, r.json())
