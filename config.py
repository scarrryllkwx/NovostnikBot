# -*- coding: utf-8 -*-
"""
Конфигурация бота-ретранслятора.

Две независимые ветки:
  1) РАКЕТНАЯ ОПАСНОСТЬ: источник MAX -> форвард в целевой MAX-канал.
  2) УГРОЗА БПЛА: источник MAX -> рерайт через нейросеть (gpt-5.6-luna,
     aitunnel.ru) -> публикация в целевой MAX-канал.

СЕКРЕТЫ здесь НЕ хранятся: токен MAX и ключ нейросети берутся из файла `.env`
рядом с этим модулем (он в .gitignore) или из переменных окружения. Шаблон —
`.env.example`. Реальные переменные окружения имеют приоритет над `.env`.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str) -> None:
    """Минимальный разбор .env (KEY=VALUE) без внешних зависимостей.

    Уже заданные переменные окружения не перезаписываются — они главнее.
    """
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.readlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(os.path.join(_HERE, ".env"))


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v if v is not None else default


# =====================  ИСТОЧНИК (MAX)  =====================================

BASE_URL = _env("MAX_BASE_URL", "https://platform-api2.max.ru")

# Токен бота MAX (подписчик источника, админ целевого MAX-канала). Из .env!
TOKEN = _env("MAX_TOKEN")

# Способ авторизации: "header" | "bearer" | "query".
AUTH_MODE = _env("MAX_AUTH_MODE", "header")

# Канал-источник (БОЕВОЙ): https://max.ru/Shapsha_VV
SOURCE_CHAT_ID = _env("MAX_SOURCE_CHAT_ID", "-68128408750804")
SOURCE_LINK = "https://max.ru/Shapsha_VV"

# --- TLS ---------------------------------------------------------------------
VERIFY_SSL = _env("MAX_VERIFY_SSL", "1") == "1"
_default_bundle = os.path.join(_HERE, "russian_trusted_bundle.pem")
CA_BUNDLE = _env("MAX_CA_BUNDLE", _default_bundle if os.path.exists(_default_bundle) else "")
USE_OS_TRUSTSTORE = _env("MAX_USE_OS_TRUSTSTORE", "1") == "1"


# =====================  ЦЕЛЬ — MAX-КАНАЛ  ==================================

MAX_TARGET_ENABLED = _env("MAX_TARGET_ENABLED", "1") == "1"
# Целевой MAX-канал (БОЕВОЙ): https://max.ru/klg_alarm «Калуга, Внимание!»
TARGET_CHAT_ID = _env("MAX_TARGET_CHAT_ID", "-68432827435555")
TARGET_LINK = "https://max.ru/klg_alarm"

# Режим для РАКЕТНОЙ ветки: "forward" (с откатом на копию) | "copy".
MAX_TARGET_MODE = _env("MAX_TARGET_MODE", "forward")


# =====================  НЕЙРОСЕТЬ ДЛЯ РЕРАЙТА (ветка БПЛА)  ================

AI_ENABLED = _env("AI_ENABLED", "1") == "1"
AI_API_KEY = _env("AI_API_KEY")  # из .env!
# aitunnel.ru — OpenAI-совместимый API
AI_BASE_URL = _env("AI_BASE_URL", "https://api.aitunnel.ru/v1")
AI_MODEL = _env("AI_MODEL", "gpt-5.6-luna")
AI_TIMEOUT = int(_env("AI_TIMEOUT", "180"))
AI_TEMPERATURE = float(_env("AI_TEMPERATURE", "0.2"))

# Проверка полноты рерайта: если в готовом посте пропало число, которое было
# в исходнике (например «42 БПЛА» или «четырёх домов» -> «4»), пост считается
# неполным и публикуется исходный текст целиком. "0" — только предупреждение.
AI_REQUIRE_ALL_NUMBERS = _env("AI_REQUIRE_ALL_NUMBERS", "1") == "1"


# =====================  ССЫЛКИ ДЛЯ ШАБЛОНОВ ПОСТОВ  ========================

# Ссылка, которая вшивается в готовый пост БПЛА в MAX.
LINK_MAX_CHANNEL = _env("LINK_MAX_CHANNEL", "https://max.ru/klg_alarm")


# =====================  ЛОГИКА ОПРОСА  =====================================

POLL_INTERVAL_SEC = int(_env("MAX_POLL_INTERVAL_SEC", "45"))
FETCH_COUNT = int(_env("MAX_FETCH_COUNT", "30"))
STATE_FILE = _env("MAX_STATE_FILE", "state.json")
LOG_FILE = _env("MAX_LOG_FILE", "bot.log")


# =====================  ТРИГГЕРЫ  ==========================================

# --- Ветка 1: ракетная опасность (форвард в MAX) ---------------------------
# Пост попадает в ветку, если содержит одну из фраз (после нормализации).
ROCKET_KEYWORDS = [
    "внимание в калужской области объявлена ракетная опасность",  # объявление
    "отбой ракетной опасности",                                   # отбой
]

# --- Ветка 2: угроза БПЛА (рерайт -> MAX) -----------------------------------
# Пост попадает в ветку, если содержит ВСЕ подстроки из списка.
# «пво уничтожен» покрывает «ПВО уничтожены/уничтожен» во всех примерах
# («Силами ПВО уничтожены 14 БПЛА…», «…уничтожен БПЛА над территорией…»).
UAV_KEYWORDS_ALL = [
    "пво уничтожен",
    "бпла",
]

NORMALIZE_BEFORE_MATCH = True
