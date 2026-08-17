# -*- coding: utf-8 -*-
"""Нормализация текста и классификация постов по веткам:
   'rocket' — ракетная опасность (объявление/отбой),
   'uav'    — угроза БПЛА (сводки «силами ПВО уничтожены N БПЛА…»),
   None     — всё остальное (игнорируется)."""

import re

import config

# Диапазоны эмодзи и служебных символов, которые убираем перед сравнением.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # пиктограммы, эмодзи
    "\U00002600-\U000027BF"  # разные символы, дингбаты
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U00002190-\U000021FF"  # стрелки
    "\U00002B00-\U00002BFF"  # доп. стрелки/символы
    "\U0000200D"             # zero width joiner
    "\U0000203C\U00002049"   # !! ?!
    "]",
    flags=re.UNICODE,
)


def normalize(text: str) -> str:
    """Приводит текст к виду, удобному для устойчивого сравнения."""
    if not text:
        return ""
    if not config.NORMALIZE_BEFORE_MATCH:
        return text
    t = _EMOJI_RE.sub(" ", text)
    t = t.lower()
    t = t.replace("ё", "е")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)  # пунктуация -> пробел
    t = re.sub(r"\s+", " ", t)                          # схлопываем пробелы/переносы
    return t.strip()


def _norm_keyword(kw: str) -> str:
    if not config.NORMALIZE_BEFORE_MATCH:
        return kw
    k = kw.lower().replace("ё", "е")
    k = re.sub(r"[^\w\s]", " ", k, flags=re.UNICODE)
    k = re.sub(r"\s+", " ", k)
    return k.strip()


_ROCKET_KW = [(_kw, _norm_keyword(_kw)) for _kw in config.ROCKET_KEYWORDS]
_UAV_KW_ALL = [_norm_keyword(_kw) for _kw in config.UAV_KEYWORDS_ALL]


def classify(text: str):
    """Возвращает ('rocket', фраза) | ('uav', None) | None.

    Ракетная ветка проверяется первой (у неё приоритет). Ветка БПЛА требует
    одновременного присутствия ВСЕХ подстрок из UAV_KEYWORDS_ALL.
    """
    norm = normalize(text)
    if not norm:
        return None

    for original, normalized in _ROCKET_KW:
        if normalized and normalized in norm:
            return ("rocket", original)

    if _UAV_KW_ALL and all(k in norm for k in _UAV_KW_ALL):
        return ("uav", None)

    return None


def matched_keyword(text: str):
    """Совместимость со старым кодом: фраза ракетной ветки или None."""
    res = classify(text)
    if res and res[0] == "rocket":
        return res[1]
    return None
