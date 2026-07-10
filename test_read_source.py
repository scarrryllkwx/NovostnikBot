# -*- coding: utf-8 -*-
"""Разовая проверка: читается ли канал-источник аккаунтом-наблюдателем."""
import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()


async def main():
    client = TelegramClient(
        "monitor_session", int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"),
        device_model="Desktop", system_version="Windows 10",
        app_version="5.6.3 x64", lang_code="ru", system_lang_code="ru-RU",
    )
    async with client:
        entity = await client.get_entity(os.getenv("SOURCE_CHANNEL"))
        print(f"Канал найден: {entity.title}")
        async for msg in client.iter_messages(entity, limit=3):
            text = (msg.message or "<без текста>").replace("\n", " ")[:80]
            print(f"  #{msg.id}: {text}")


asyncio.run(main())
