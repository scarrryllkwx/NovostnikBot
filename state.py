# -*- coding: utf-8 -*-
"""Хранение состояния между опросами/перезапусками: какие mid уже обработаны
и до какой метки времени мы дочитали источник."""

import json
import os
import logging

import config

log = logging.getLogger("state")


class State:
    def __init__(self, path: str = None):
        self.path = path or config.STATE_FILE
        self.last_ts = None
        # множество обработанных mid; ограничиваем размер, чтобы файл не рос вечно
        self.seen_mids = []
        self._seen_set = set()
        self._max_seen = 2000
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.last_ts = data.get("last_ts")
            self.seen_mids = data.get("seen_mids", [])
            self._seen_set = set(self.seen_mids)
            log.info("Загружено состояние: last_ts=%s, seen=%d", self.last_ts, len(self.seen_mids))
        except Exception as e:
            log.warning("Не удалось прочитать состояние (%s): %s", self.path, e)

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(
                    {"last_ts": self.last_ts, "seen_mids": self.seen_mids},
                    f,
                    ensure_ascii=False,
                )
            os.replace(tmp, self.path)
        except Exception as e:
            log.warning("Не удалось сохранить состояние: %s", e)

    def is_seen(self, mid) -> bool:
        return mid in self._seen_set

    def mark_seen(self, mid):
        if mid in self._seen_set:
            return
        self._seen_set.add(mid)
        self.seen_mids.append(mid)
        # обрезаем историю
        if len(self.seen_mids) > self._max_seen:
            drop = self.seen_mids[:-self._max_seen]
            self.seen_mids = self.seen_mids[-self._max_seen:]
            for m in drop:
                self._seen_set.discard(m)

    def update_ts(self, ts):
        if ts is None:
            return
        if self.last_ts is None or ts > self.last_ts:
            self.last_ts = ts
