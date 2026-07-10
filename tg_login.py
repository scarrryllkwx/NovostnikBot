# -*- coding: utf-8 -*-
"""Пошаговая авторизация аккаунта-наблюдателя Telegram (Telethon).

Шаг 1: python tg_login.py request +79991234567   -> Telegram пришлёт код
Шаг 2: python tg_login.py confirm 12345          -> вход по коду
Шаг 3 (только если включена двухэтапная защита):
        python tg_login.py password ВашОблачныйПароль
"""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

load_dotenv()
STATE_FILE = "login_state.json"


async def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        return
    action, value = sys.argv[1], sys.argv[2]

    # Те же параметры устройства, что и в bot.py — сессия выглядит как Telegram Desktop
    client = TelegramClient(
        "monitor_session", int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"),
        device_model="Desktop",
        system_version="Windows 10",
        app_version="5.6.3 x64",
        lang_code="ru",
        system_lang_code="ru-RU",
    )
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Уже авторизован как: {me.first_name} (+{me.phone})")
        await client.disconnect()
        return

    if action == "request":
        sent = await client.send_code_request(value)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"phone": value, "hash": sent.phone_code_hash}, f)
        print("Код отправлен. Проверьте Telegram и выполните: python tg_login.py confirm КОД")

    elif action == "confirm":
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
        try:
            await client.sign_in(state["phone"], value, phone_code_hash=state["hash"])
            me = await client.get_me()
            print(f"Успешно! Авторизован как: {me.first_name} (+{me.phone})")
        except SessionPasswordNeededError:
            print("Включена двухэтапная защита. Выполните: python tg_login.py password ВАШ_ПАРОЛЬ")

    elif action == "password":
        await client.sign_in(password=value)
        me = await client.get_me()
        print(f"Успешно! Авторизован как: {me.first_name} (+{me.phone})")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
