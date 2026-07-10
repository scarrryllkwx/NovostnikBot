# -*- coding: utf-8 -*-
"""Разовая проверка: может ли MAX-бот публиковать в целевой канал."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("MAX_BOT_TOKEN")
chat_id = os.getenv("MAX_CHAT_ID")

r = requests.post(
    f"https://platform-api.max.ru/messages?chat_id={chat_id}",
    headers={"Authorization": token},
    json={"text": "Тестовое сообщение: проверка прав бота. Можно удалить."},
    timeout=30,
)
print(r.status_code, r.json())
