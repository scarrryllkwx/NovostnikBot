# -*- coding: utf-8 -*-
"""
Бот "Ракетная опасность"
Мониторит канал губернатора в Telegram, при обнаружении ключевой фразы
делает минимальный рерайт через нейросеть (aitunnel) и публикует
в ваши каналы в Telegram и MAX.
"""

import asyncio
import html
import logging
import os
import re

import aiohttp
from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

# ---------- Настройки из .env ----------
TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "")          # канал губернатора, напр. @gubernator_xx

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")              # токен вашего бота от @BotFather
TG_TARGET_CHANNEL = os.getenv("TG_TARGET_CHANNEL", "")    # ваш канал, напр. @moy_kanal или -100...

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "")            # токен бота MAX от @MasterBot
MAX_CHAT_ID = os.getenv("MAX_CHAT_ID", "")                # chat_id вашего канала в MAX

AITUNNEL_API_KEY = os.getenv("AITUNNEL_API_KEY", "")
AITUNNEL_MODEL = os.getenv("AITUNNEL_MODEL", "gpt-4o-mini")
AITUNNEL_URL = "https://api.aitunnel.ru/v1/chat/completions"

# Ловим "ракетная опасность" в любом регистре, включая опечатку "рокетная",
# а также падежные формы ("ракетной опасности" — отбой тоже поймается)
KEYWORD_RE = re.compile(r"р[ао]кетн\w*\s+опасн", re.IGNORECASE)

REWRITE_PROMPT = (
    "Ты — редактор канала экстренных оповещений. Тебе дают официальное сообщение "
    "о ракетной опасности или её отбое. Сделай МИНИМАЛЬНЫЙ рерайт: слегка измени "
    "формулировки и порядок слов, чтобы текст не был дословной копией оригинала. "
    "Строгие правила:\n"
    "1. Сохрани абсолютно все факты: названия населённых пунктов и районов, время, "
    "даты, инструкции для жителей — без малейших изменений.\n"
    "2. Ничего не добавляй от себя и ничего не удаляй по смыслу.\n"
    "3. Сохрани тон и срочность сообщения, эмодзи оставь как есть.\n"
    "4. Объём текста должен остаться примерно тем же.\n"
    "5. В ответе выдай ТОЛЬКО переписанный текст, без кавычек, пояснений и комментариев."
)

# Подпись под текстом оповещения (одинаковая в обоих мессенджерах)
SIGNATURE = "— Владислав Шапша"

# Подвалы со встроенными ссылками. Разные для каждого мессенджера.
# Формат HTML: <a href="ссылка">текст</a>
MAX_FOOTER = (
    '<a href="https://max.ru/klg_alarm">📍Калуга, внимание</a>'
)
TG_FOOTER = (
    '📌 <a href="https://max.ru/klg_alarm">Подписывайтесь на нас в MAX</a>\n\n'
    '<a href="https://t.me/boost/klg_alarm">Наш канал в MAX</a>'
    '🔴 <a href="https://t.me/boost/klg_alarm">Поддержать канал</a>'
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")],
)
log = logging.getLogger("rocket-bot")


async def rewrite_text(session: aiohttp.ClientSession, text: str) -> str:
    """Минимальный рерайт через aitunnel. При любой ошибке возвращает оригинал —
    оповещение важнее рерайта."""
    payload = {
        "model": AITUNNEL_MODEL,
        "messages": [
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {AITUNNEL_API_KEY}"}
    try:
        async with session.post(AITUNNEL_URL, json=payload, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=45)) as resp:
            data = await resp.json()
            if resp.status == 200:
                result = data["choices"][0]["message"]["content"].strip()
                if result:
                    return result
            log.error("Ошибка рерайта (HTTP %s): %s", resp.status, data)
    except Exception:
        log.exception("Не удалось сделать рерайт, публикую оригинал")
    return text


async def send_telegram(session: aiohttp.ClientSession, text: str) -> None:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_TARGET_CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with session.post(url, json=payload,
                                timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            if data.get("ok"):
                log.info("Опубликовано в Telegram-канал %s", TG_TARGET_CHANNEL)
            else:
                log.error("Telegram отказал: %s", data)
    except Exception:
        log.exception("Ошибка отправки в Telegram")


async def send_max(session: aiohttp.ClientSession, text: str) -> None:
    url = f"https://platform-api.max.ru/messages?chat_id={MAX_CHAT_ID}"
    headers = {"Authorization": MAX_BOT_TOKEN}
    payload = {"text": text, "format": "html"}
    try:
        async with session.post(url, json=payload, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            if resp.status == 200:
                log.info("Опубликовано в MAX-канал %s", MAX_CHAT_ID)
            else:
                log.error("MAX отказал (HTTP %s): %s", resp.status, data)
    except Exception:
        log.exception("Ошибка отправки в MAX")


# Параметры устройства: сессия выглядит как обычный Telegram Desktop.
# Должны быть одинаковыми во всех скриптах и никогда не меняться.
DEVICE_PARAMS = dict(
    device_model="Desktop",
    system_version="Windows 10",
    app_version="5.6.3 x64",
    lang_code="ru",
    system_lang_code="ru-RU",
)


async def main() -> None:
    client = TelegramClient("monitor_session", TG_API_ID, TG_API_HASH, **DEVICE_PARAMS)
    http = aiohttp.ClientSession()
    processed: set[int] = set()

    @client.on(events.NewMessage(chats=SOURCE_CHANNEL))
    async def handler(event):
        text = event.message.message or ""
        if not text or not KEYWORD_RE.search(text):
            return
        if event.message.id in processed:
            return
        processed.add(event.message.id)

        log.info("Поймано сообщение #%s: %.80s...", event.message.id, text)
        rewritten = await rewrite_text(http, text)
        # Экранируем текст оповещения: он идёт в HTML-режиме, спецсимволы < > &
        # не должны ломать разметку. Ссылки в подвалах уже валидный HTML.
        body = html.escape(rewritten)
        # Подпись и подвал добавляем после рерайта. Подвал свой для каждого мессенджера.
        tg_text = f"{body}\n\n{SIGNATURE}\n\n{TG_FOOTER}"
        max_text = f"{body}\n\n{SIGNATURE}\n\n{MAX_FOOTER}"
        # Публикуем в оба мессенджера параллельно
        await asyncio.gather(
            send_telegram(http, tg_text),
            send_max(http, max_text),
        )

    async with client:
        log.info("Бот запущен. Слежу за каналом %s", SOURCE_CHANNEL)
        try:
            await client.run_until_disconnected()
        finally:
            await http.close()


if __name__ == "__main__":
    asyncio.run(main())
