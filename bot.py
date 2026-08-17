# -*- coding: utf-8 -*-
"""
Бот-ретранслятор с двумя ветками обработки постов канала-источника MAX:

  1) РАКЕТНАЯ ОПАСНОСТЬ (объявление/отбой) -> форвард в целевой MAX-канал.
  2) УГРОЗА БПЛА (сводки «силами ПВО уничтожены N БПЛА…») -> рерайт через
     нейросеть -> публикация в целевой MAX-канал.

Все прочие посты источника игнорируются.

Режимы запуска:
    python bot.py --me           проверить токен MAX (GET /me)
    python bot.py --chats        показать чаты бота с их chat_id
    python bot.py --seed         пометить текущие посты обработанными БЕЗ
                                  публикации (один раз перед первым --loop)
    python bot.py --check        разовый GET /messages по источнику (сырой JSON)
    python bot.py --once         один проход опроса
    python bot.py --loop         рабочий режим: бесконечный опрос
    python bot.py --dry-run      с --once/--loop: находит и рерайтит, но НЕ
                                  публикует (печатает результат в лог)
"""

import sys
import json
import time
import logging

# На Windows консоль часто в cp1251 и падает на эмодзи. Принудительно UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
import matcher
import parsing
import publishers
import rewriter
from max_api import MaxClient, MaxApiError
from state import State

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)

try:
    _fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    _fh.setFormatter(logging.Formatter(_LOG_FORMAT))
    logging.getLogger().addHandler(_fh)
except Exception as _e:
    logging.getLogger("bot").warning("Не удалось открыть файл лога: %s", _e)

log = logging.getLogger("bot")


# ---------------------------------------------------------------------------
# Сервисные команды
# ---------------------------------------------------------------------------

def cmd_me(client: MaxClient):
    try:
        print(json.dumps(client.get_me(), ensure_ascii=False, indent=2))
    except MaxApiError as e:
        log.error("Ошибка /me: %s", e)
        sys.exit(1)


def cmd_chats(client: MaxClient):
    try:
        resp = client.get_chats()
    except MaxApiError as e:
        log.error("Ошибка /chats: %s", e)
        sys.exit(1)
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    chats = parsing.extract_chat_list(resp)
    if chats:
        log.info("Найдено чатов: %d", len(chats))
        for c in chats:
            log.info("  chat_id=%s | title=%r | link=%s",
                     parsing.get_chat_id(c), parsing.get_chat_title(c), parsing.get_chat_link(c))


def cmd_seed(client: MaxClient, st: State):
    """Помечает все текущие посты источника обработанными БЕЗ публикации."""
    if not config.SOURCE_CHAT_ID:
        log.error("Не задан SOURCE_CHAT_ID.")
        sys.exit(1)
    try:
        resp = client.get_messages(config.SOURCE_CHAT_ID, count=config.FETCH_COUNT)
    except MaxApiError as e:
        log.error("Ошибка GET /messages: %s", e)
        sys.exit(1)
    msgs = parsing.extract_message_list(resp)
    n = 0
    for m in msgs:
        mid = parsing.get_mid(m)
        if mid:
            st.mark_seen(mid)
            st.update_ts(parsing.get_timestamp(m))
            n += 1
    st.save()
    log.info("Засеяно состояние: помечено обработанными %d постов. "
             "Теперь --loop будет реагировать только на новые.", n)


def cmd_check(client: MaxClient):
    if not config.SOURCE_CHAT_ID:
        log.error("Не задан SOURCE_CHAT_ID.")
        sys.exit(1)
    try:
        resp = client.get_messages(config.SOURCE_CHAT_ID, count=config.FETCH_COUNT)
    except MaxApiError as e:
        log.error("Ошибка GET /messages: %s", e)
        sys.exit(1)
    print(json.dumps(resp, ensure_ascii=False, indent=2))
    msgs = parsing.extract_message_list(resp)
    log.info("Распознано сообщений в ответе: %d", len(msgs))


# ---------------------------------------------------------------------------
# Обработка постов
# ---------------------------------------------------------------------------

def handle_rocket(client: MaxClient, mid, text: str, dry_run: bool) -> bool:
    if dry_run:
        log.info("[dry-run] РАКЕТА: форварднул бы mid=%s в MAX.", mid)
        return True
    return publishers.publish_rocket(client, mid, text)


def handle_uav(client: MaxClient, mid, text: str, dry_run: bool) -> bool:
    """Рерайт поста про БПЛА и публикация в целевой MAX-канал."""
    max_html = None
    if config.AI_ENABLED:
        try:
            max_html = rewriter.build_max_post(text)
        except rewriter.RewriteError as e:
            log.error("БПЛА: рерайт не удался (%s) — публикую исходный текст.", e)

    if max_html is None:
        # fallback: исходный текст без рерайта (плоским текстом)
        if dry_run:
            log.info("[dry-run] БПЛА: опубликовал бы исходный текст (mid=%s).", mid)
            return True
        try:
            client.send_text(config.TARGET_CHAT_ID, text)
            log.info("БПЛА/MAX: опубликован исходный текст (fallback), mid=%s", mid)
            return True
        except MaxApiError as e:
            log.error("БПЛА/MAX: fallback-публикация не удалась: %s", e)
            return False

    if dry_run:
        log.info("[dry-run] БПЛА: опубликовал бы (mid=%s).\n--- MAX ---\n%s", mid, max_html)
        return True

    return publishers.publish_uav_max(client, max_html)


def poll_once(client: MaxClient, st: State, dry_run: bool) -> int:
    try:
        # Параметр `from` в MAX листает в историю (старее метки), поэтому просто
        # берём последние N сообщений; от повторов защищает список seen_mids.
        resp = client.get_messages(config.SOURCE_CHAT_ID, count=config.FETCH_COUNT)
    except MaxApiError as e:
        log.error("Опрос источника не удался: %s", e)
        return 0

    msgs = parsing.extract_message_list(resp)
    if not msgs:
        return 0

    msgs_sorted = sorted(msgs, key=lambda m: parsing.get_timestamp(m) or 0)

    published = 0
    for msg in msgs_sorted:
        mid = parsing.get_mid(msg)
        ts = parsing.get_timestamp(msg)
        text = parsing.get_text(msg)

        if mid is None or st.is_seen(mid):
            continue

        verdict = matcher.classify(text)
        if verdict is None:
            st.mark_seen(mid)
            st.update_ts(ts)
            continue

        branch, kw = verdict
        if branch == "rocket":
            log.info("РАКЕТА: совпадение по фразе %r, mid=%s", kw, mid)
            ok = handle_rocket(client, mid, text, dry_run)
        else:
            log.info("БПЛА: совпадение, mid=%s", mid)
            ok = handle_uav(client, mid, text, dry_run)

        if ok:
            published += 1
        st.mark_seen(mid)
        st.update_ts(ts)

    st.save()
    return published


def cmd_loop(client: MaxClient, st: State, dry_run: bool, once: bool):
    if not config.SOURCE_CHAT_ID:
        log.error("Не задан SOURCE_CHAT_ID.")
        sys.exit(1)

    log.info(
        "Старт. Источник=%s | Ракеты->MAX(%s) форвард | БПЛА->MAX рерайт | Интервал=%ss%s",
        config.SOURCE_CHAT_ID,
        config.TARGET_CHAT_ID,
        config.POLL_INTERVAL_SEC,
        " [dry-run]" if dry_run else "",
    )

    while True:
        try:
            n = poll_once(client, st, dry_run)
            if n:
                log.info("За проход обработано постов: %d", n)
        except Exception as e:
            log.exception("Непредвиденная ошибка в проходе: %s", e)
        if once:
            break
        time.sleep(config.POLL_INTERVAL_SEC)


def main():
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args

    if not config.TOKEN:
        log.error(
            "Не задан токен MAX. Скопируйте .env.example в .env и впишите "
            "MAX_TOKEN (и AI_API_KEY для рерайта)."
        )
        sys.exit(1)
    if config.AI_ENABLED and not config.AI_API_KEY:
        log.warning(
            "AI_API_KEY не задан — рерайт отключён, посты о БПЛА пойдут "
            "исходным текстом."
        )

    client = MaxClient()
    st = State()

    if "--me" in args:
        cmd_me(client)
    elif "--chats" in args:
        cmd_chats(client)
    elif "--seed" in args:
        cmd_seed(client, st)
    elif "--check" in args:
        cmd_check(client)
    elif "--once" in args:
        cmd_loop(client, st, dry_run, once=True)
    elif "--loop" in args or not args:
        cmd_loop(client, st, dry_run, once=False)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
