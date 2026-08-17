# -*- coding: utf-8 -*-
"""Публикация постов по веткам (обе цели — целевой MAX-канал).

Ветка «ракетная опасность»: форвард (при неудаче — копия текста).
Ветка «БПЛА»: отрерайченный пост (HTML, при отказе разметки — плоский текст).
"""

import logging

import config
import rewriter
from max_api import MaxClient, MaxApiError

log = logging.getLogger("publishers")


# ---------------------------------------------------------------------------
# Ветка 1: ракетная опасность -> MAX (форвард)
# ---------------------------------------------------------------------------

def publish_rocket(client: MaxClient, mid, text: str) -> bool:
    """Форвард ракетного поста в целевой MAX-канал; при неудаче — копия."""
    if not (config.MAX_TARGET_ENABLED and config.TARGET_CHAT_ID):
        log.error("MAX-цель не настроена — ракетный пост не опубликован.")
        return False

    if config.MAX_TARGET_MODE == "forward" and mid:
        try:
            client.send_forward(config.TARGET_CHAT_ID, mid)
            log.info("РАКЕТА/MAX: форвард в %s (mid=%s)", config.TARGET_CHAT_ID, mid)
            return True
        except MaxApiError as e:
            log.warning("РАКЕТА/MAX: форвард не удался (%s) — копирую текст.", e)

    try:
        client.send_text(config.TARGET_CHAT_ID, text)
        log.info("РАКЕТА/MAX: копия текста в %s", config.TARGET_CHAT_ID)
        return True
    except MaxApiError as e:
        log.error("РАКЕТА/MAX: публикация не удалась: %s", e)
        return False


# ---------------------------------------------------------------------------
# Ветка 2: БПЛА -> MAX (отрерайченный текст)
# ---------------------------------------------------------------------------

def publish_uav_max(client: MaxClient, max_html: str) -> bool:
    if not (config.MAX_TARGET_ENABLED and config.TARGET_CHAT_ID):
        log.error("MAX-цель не настроена — пост БПЛА не опубликован.")
        return False
    try:
        client.send_text(config.TARGET_CHAT_ID, max_html, fmt="html")
        log.info("БПЛА/MAX: опубликовано (html) в %s", config.TARGET_CHAT_ID)
        return True
    except MaxApiError as e:
        log.warning("БПЛА/MAX: html не принят (%s), отправляю плоским текстом.", e)
    try:
        client.send_text(config.TARGET_CHAT_ID, rewriter.strip_html(max_html))
        log.info("БПЛА/MAX: опубликовано плоским текстом.")
        return True
    except MaxApiError as e:
        log.error("БПЛА/MAX: публикация не удалась: %s", e)
        return False
