# -*- coding: utf-8 -*-
"""Вспомогательный скрипт: показывает список чатов/каналов, где состоит ваш MAX-бот,
чтобы узнать chat_id канала для .env (MAX_CHAT_ID).
Запуск: python max_get_chat_id.py"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("MAX_BOT_TOKEN", "")
resp = requests.get("https://platform-api.max.ru/chats",
                    headers={"Authorization": token}, timeout=30)
data = resp.json()

if resp.status_code != 200:
    print("Ошибка:", data)
else:
    for chat in data.get("chats", []):
        print(f"chat_id: {chat.get('chat_id')} | тип: {chat.get('type')} | название: {chat.get('title')}")
    if not data.get("chats"):
        print("Чатов не найдено. Убедитесь, что бот добавлен в канал как администратор.")
