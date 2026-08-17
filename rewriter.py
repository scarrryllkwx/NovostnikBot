# -*- coding: utf-8 -*-
"""Рерайт постов про БПЛА через нейросеть (OpenAI-совместимый API aitunnel.ru).

Схема надёжности: нейросеть возвращает ТОЛЬКО содержательные части (заголовок,
тело, цитату) в JSON — а финальная разметка (жирный, «цитата», ссылка) собирается
детерминированно в коде. Так LLM не может сломать форматирование или потерять
обязательную ссылку.

Если нейросеть недоступна/ответила мусором — вызывающая сторона публикует
исходный текст без рерайта (доставка информации важнее красоты).
"""

import json
import logging
import re

import requests

import config

log = logging.getLogger("rewriter")


class RewriteError(Exception):
    pass


# ---------------------------------------------------------------------------
# Вызов нейросети
# ---------------------------------------------------------------------------

def _post(payload: dict):
    url = f"{config.AI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        return requests.post(url, headers=headers, json=payload, timeout=config.AI_TIMEOUT)
    except requests.RequestException as e:
        raise RewriteError(f"Сеть/таймаут при обращении к нейросети: {e}")


def _chat(system_prompt: str, user_text: str) -> str:
    payload = {
        "model": config.AI_MODEL,
        "temperature": config.AI_TEMPERATURE,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }
    resp = _post(payload)

    # Рассуждающие модели (gpt-5.x) не принимают temperature != 1 и могут не
    # поддерживать response_format — повторяем запрос без спорных параметров.
    if resp.status_code >= 400:
        body = resp.text[:300]
        retry = dict(payload)
        if "temperature" in body:
            retry.pop("temperature", None)
        if "response_format" in body:
            retry.pop("response_format", None)
        if retry != payload:
            log.warning("Нейросеть отклонила параметры (%s) — повтор без них.", body)
            resp = _post(retry)

    if resp.status_code >= 400:
        raise RewriteError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as e:
        raise RewriteError(f"Неожиданный ответ нейросети: {e}: {resp.text[:300]}")


def _parse_json(content: str) -> dict:
    """Достаёт JSON из ответа модели (в т.ч. если она обернула его в ```)."""
    s = content.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        raise RewriteError(f"В ответе нейросети нет JSON: {content[:200]}")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise RewriteError(f"Невалидный JSON от нейросети: {e}: {content[:200]}")


# ---------------------------------------------------------------------------
# Промпт (формат MAX)
# ---------------------------------------------------------------------------

_MAX_SYSTEM = """Ты — редактор новостного канала о происшествиях в Калужской области.
Тебе дают официальный пост губернатора о сбитых БПЛА. Перепиши его части для поста
в мессенджере MAX.

ГЛАВНОЕ ПРАВИЛО: ни один факт исходника не должен пропасть. Это сводка о ЧС —
потеря сведений о повреждениях, пострадавших, эвакуации, отмене занятий, работе
служб или мерах помощи недопустима. Ты сокращаешь формулировки, а не содержание.
Числа, названия округов и населённых пунктов переноси буква в букву, без опечаток
и без округления.

Верни СТРОГО JSON без пояснений, вида:
{"headline": "...", "body": "...", "details": ["...", "..."], "quote": "..."}

headline:
- Формат: «N БПЛА уничтожены <время> силами ПВО над регионом».
- <время> возьми из исходника («вчера вечером и сегодня ночью», «минувшей ночью»,
  «в течение дня» и т.п.); если времени в исходнике нет — просто
  «N БПЛА уничтожены силами ПВО над регионом».
- Если БПЛА один: «БПЛА уничтожен <время> силами ПВО над регионом».
- Всегда «над регионом» в единственном числе. Без эмодзи, без точки в конце.

body:
- Формат: «Их сбили над <округа в творительном падеже> округами, а также на окраине
  <города>.» — хвост про окраину только если он есть в исходнике.
- Если БПЛА один: «Его сбили над <округом>…».
- Перечисли ВСЕ округа из исходника в том же порядке и с теми же названиями
  (проверь каждое название по букве). Убери слова «территориями» и «муниципальных».
- Заверши точкой.

details — массив абзацев (0, 1 или несколько):
- Сюда идёт ВСЯ остальная содержательная информация исходника, которая не попала
  в headline, body и quote: повреждения имущества, число и тип пострадавших объектов,
  наличие или отсутствие пострадавших людей, эвакуация, возгорания, обещанная помощь,
  ограничения, просьбы к жителям, рекомендации.
- Каждый абзац — короткое ясное предложение или два, деловым тоном, без эмодзи.
  Сохраняй все числа и привязку к месту («в Боровском округе»).
- Формулировку «По предварительной информации» сохраняй, если она есть в исходнике.
- Если в исходнике действительно нет ничего кроме удара и работы служб — верни [].
- Не выдумывай ничего, чего нет в исходнике.

quote:
- Дословный абзац исходника про работу оперативных групп/экстренных служб
  (обычно последний). Без кавычек, без точки в конце.
- Если такого абзаца нет — верни пустую строку, а прочие сведения положи в details.
- Один и тот же факт не должен быть и в quote, и в details.
"""


# ---------------------------------------------------------------------------
# Сборка финального поста (разметка и ссылка — только в коде)
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    """Экранирование HTML-спецсимволов в тексте от нейросети."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").strip()


def assemble_max(headline: str, body: str, quote: str, details=None) -> str:
    blocks = [f"<b>⚡ {_esc(headline)}</b>", _esc(body)]

    for para in _as_paragraphs(details):
        blocks.append(_esc(para))

    if quote and quote.strip():
        blocks.append(f"«{_esc(quote)}», - Владислав Шапша.")

    blocks.append(
        f"\U0001F4CD <a href=\"{config.LINK_MAX_CHANNEL}\">Калуга, внимание</a>"
    )
    return "\n\n".join(blocks)


def _as_paragraphs(details) -> list:
    """details от нейросети: список абзацев, строка или None."""
    if not details:
        return []
    if isinstance(details, str):
        parts = [p.strip() for p in details.split("\n")]
    elif isinstance(details, list):
        parts = [str(p).strip() for p in details]
    else:
        return []
    return [p for p in parts if p]


def strip_html(s: str) -> str:
    """Fallback: превращает HTML-пост в плоский текст (если html не принят)."""
    s = re.sub(r"<a href=\"([^\"]+)\">([^<]+)</a>", r"\2 (\1)", s)
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


# ---------------------------------------------------------------------------
# Публичный API модуля
# ---------------------------------------------------------------------------

def _lost_numbers(source_text: str, post: str) -> list:
    """Числа исходника, не попавшие в готовый пост (признак потери фактов)."""
    in_post = set(re.findall(r"\d+", post))
    lost = []
    for num in re.findall(r"\d+", source_text):
        if num not in in_post and num not in lost:
            lost.append(num)
    return lost


def build_max_post(source_text: str) -> str:
    """Возвращает готовый HTML-пост для MAX.

    Бросает RewriteError, если нейросеть недоступна или потеряла факты —
    решение о fallback (публикация исходника) принимает вызывающая сторона.
    """
    mx = _parse_json(_chat(_MAX_SYSTEM, source_text))
    if not mx.get("headline") or not mx.get("body"):
        raise RewriteError(f"Неполный JSON для MAX: {mx}")

    post = assemble_max(
        mx["headline"], mx["body"], mx.get("quote", ""), mx.get("details")
    )

    lost = _lost_numbers(source_text, post)
    if lost:
        if config.AI_REQUIRE_ALL_NUMBERS:
            raise RewriteError(
                "рерайт потерял числа исходника: %s" % ", ".join(lost)
            )
        log.warning("Рерайт потерял числа исходника: %s", ", ".join(lost))

    return post
