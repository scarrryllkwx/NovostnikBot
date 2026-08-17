# -*- coding: utf-8 -*-
"""Тонкая обёртка над HTTP API мессенджера MAX.

Все места, где формат ответа/запроса в документации неоднозначен, снабжены
комментарием [ПРОВЕРИТЬ] и написаны «терпимо» к вариациям структуры.
"""

import time
import logging

import requests

import config

log = logging.getLogger("max_api")

# MAX использует «Russian Trusted CA». Если в системе (Windows) этот корневой
# сертификат установлен, пакет truststore позволяет requests проверять цепочку
# через системное хранилище — безопасно и без отключения проверки.
if config.USE_OS_TRUSTSTORE and not config.CA_BUNDLE:
    try:
        import truststore
        truststore.inject_into_ssl()
        log.info("truststore подключён: TLS проверяется через хранилище ОС.")
    except Exception as e:
        log.debug("truststore недоступен (%s). Будет использовано хранилище по умолчанию.", e)


class MaxApiError(Exception):
    pass


class MaxClient:
    def __init__(self):
        self.base_url = config.BASE_URL.rstrip("/")
        self.token = config.TOKEN
        self.auth_mode = config.AUTH_MODE
        self.session = requests.Session()
        # Настройка проверки TLS: путь к CA-бандлу, True или False.
        if config.CA_BUNDLE:
            self.verify = config.CA_BUNDLE
        else:
            self.verify = config.VERIFY_SSL
        if self.verify is False:
            log.warning("Проверка TLS-сертификата MAX ОТКЛЮЧЕНА (MAX_VERIFY_SSL=0).")
            try:
                requests.packages.urllib3.disable_warnings()
            except Exception:
                pass

    # --- вспомогательное ----------------------------------------------------

    def _headers(self):
        if self.auth_mode == "header":
            return {"Authorization": self.token}
        if self.auth_mode == "bearer":
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def _params(self, extra: dict) -> dict:
        params = dict(extra or {})
        if self.auth_mode == "query":
            params["access_token"] = self.token
        return params

    def _request(self, method: str, path: str, params=None, json=None, retries=3):
        url = f"{self.base_url}{path}"
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=self._params(params),
                    json=json,
                    timeout=20,
                    verify=self.verify,
                )
            except requests.RequestException as e:
                last_err = e
                log.warning("Сетевая ошибка (%s/%s): %s", attempt, retries, e)
                time.sleep(min(2 ** attempt, 10))
                continue

            # 429 / 5xx — временные, повторяем с бэкоффом.
            if resp.status_code == 429 or resp.status_code >= 500:
                last_err = MaxApiError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                wait = min(2 ** attempt, 15)
                log.warning("Временная ошибка HTTP %s, повтор через %ss", resp.status_code, wait)
                time.sleep(wait)
                continue

            if resp.status_code >= 400:
                raise MaxApiError(f"HTTP {resp.status_code}: {resp.text[:500]}")

            if not resp.text:
                return {}
            try:
                return resp.json()
            except ValueError:
                raise MaxApiError(f"Ответ не JSON: {resp.text[:300]}")

        raise MaxApiError(f"Не удалось выполнить {method} {path}: {last_err}")

    # --- методы API ---------------------------------------------------------

    def get_me(self):
        """Проверка токена. [ПРОВЕРИТЬ] путь /me — стандартный для MAX Bot API."""
        return self._request("GET", "/me")

    def get_chats(self, count: int = 100):
        """Список чатов/каналов, где состоит бот. Нужен, чтобы узнать числовые
        chat_id источника и цели по их ссылкам. [ПРОВЕРИТЬ] путь /chats."""
        return self._request("GET", "/chats", params={"count": count})

    def get_messages(self, chat_id: str, count: int = None, since_ts=None):
        """Читает историю чата/канала.

        [ПРОВЕРИТЬ] Имена параметров: chat_id, count, from. По документации MAX
        `from`/`to` — это метки времени. Если реальный ответ отличается —
        поправим здесь в одном месте.
        """
        params = {"chat_id": chat_id}
        if count:
            params["count"] = count
        if since_ts is not None:
            params["from"] = since_ts
        return self._request("GET", "/messages", params=params)

    def send_forward(self, chat_id: str, mid: str):
        """Публикует пост как форвард (link.type = forward)."""
        body = {"link": {"type": "forward", "mid": mid}}
        return self._request("POST", "/messages", params={"chat_id": chat_id}, json=body)

    def send_text(self, chat_id: str, text: str, fmt: str = None):
        """Публикует текстовое сообщение. fmt: None | "html" | "markdown"."""
        body = {"text": text}
        if fmt:
            body["format"] = fmt
        return self._request("POST", "/messages", params={"chat_id": chat_id}, json=body)
