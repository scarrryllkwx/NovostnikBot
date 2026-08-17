# -*- coding: utf-8 -*-
"""Извлечение списка сообщений и их полей из ответа GET /messages.

Формат ответа MAX точно не зафиксирован, поэтому здесь всё сделано максимально
терпимо: список сообщений ищется под несколькими возможными ключами, а mid /
text / timestamp — тоже по нескольким вариантам расположения. После первого
реального ответа от API оставим только фактический вариант.
"""


def extract_message_list(resp):
    """Достаёт список сообщений из ответа независимо от обёртки."""
    if resp is None:
        return []
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for key in ("messages", "result", "items", "data"):
            v = resp.get(key)
            if isinstance(v, list):
                return v
        # иногда payload вложен: {"result": {"messages": [...]}}
        for key in ("result", "data"):
            inner = resp.get(key)
            if isinstance(inner, dict):
                for k2 in ("messages", "items"):
                    if isinstance(inner.get(k2), list):
                        return inner[k2]
    return []


def get_mid(msg: dict):
    """Идентификатор сообщения (message id)."""
    if not isinstance(msg, dict):
        return None
    body = msg.get("body")
    if isinstance(body, dict) and body.get("mid"):
        return body["mid"]
    for key in ("mid", "message_id", "id"):
        if msg.get(key):
            return msg[key]
    return None


def get_text(msg: dict) -> str:
    """Текст сообщения."""
    if not isinstance(msg, dict):
        return ""
    body = msg.get("body")
    if isinstance(body, dict):
        for key in ("text", "message", "caption"):
            if isinstance(body.get(key), str):
                return body[key]
    for key in ("text", "message", "caption"):
        if isinstance(msg.get(key), str):
            return msg[key]
    return ""


def extract_chat_list(resp):
    """Достаёт список чатов из ответа GET /chats независимо от обёртки."""
    if resp is None:
        return []
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for key in ("chats", "result", "items", "data"):
            v = resp.get(key)
            if isinstance(v, list):
                return v
    return []


def get_chat_id(chat: dict):
    if not isinstance(chat, dict):
        return None
    for key in ("chat_id", "id", "chatId"):
        if chat.get(key) is not None:
            return chat[key]
    return None


def get_chat_title(chat: dict) -> str:
    if not isinstance(chat, dict):
        return ""
    for key in ("title", "name"):
        if isinstance(chat.get(key), str):
            return chat[key]
    return ""


def get_chat_link(chat: dict) -> str:
    if not isinstance(chat, dict):
        return ""
    for key in ("link", "url", "username"):
        if isinstance(chat.get(key), str):
            return chat[key]
    return ""


def get_timestamp(msg: dict):
    """Метка времени сообщения (как есть, обычно миллисекунды)."""
    if not isinstance(msg, dict):
        return None
    for key in ("timestamp", "time", "date", "updated_at", "created_at"):
        v = msg.get(key)
        if isinstance(v, (int, float)):
            return int(v)
    return None
