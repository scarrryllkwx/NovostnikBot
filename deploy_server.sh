#!/bin/bash
# Обновление боевого бота на сервере из репозитория.
# Запускать НА СЕРВЕРЕ:  bash deploy_server.sh
#
# Что делает: останавливает сервис, делает резервную копию, подтягивает код
# из GitHub, сохраняет .env и state.json, обновляет зависимости, проверяет
# токен и поднимает сервис обратно.

set -e

DIR=/root/NovostnikAllertBot
REPO=https://github.com/scarrryllkwx/NovostnikBot.git
SERVICE=novostnik-allert-bot
BAK="/root/NovostnikAllertBot.bak.$(date +%F-%H%M%S)"

echo "==> Останавливаю сервис"
systemctl stop "$SERVICE"

echo "==> Резервная копия: $BAK"
cp -a "$DIR" "$BAK"

echo "==> Обновляю код"
cd "$DIR"
if [ -d .git ]; then
    git fetch origin
    git reset --hard origin/main
else
    # Папка разворачивалась копированием — подкладываем репозиторий,
    # сохраняя .env, state.json и venv.
    TMP=$(mktemp -d)
    git clone --depth 1 "$REPO" "$TMP/repo"
    cp -a "$TMP/repo/." "$DIR/"
    rm -rf "$TMP"
fi

echo "==> Проверяю секреты"
if [ ! -f "$DIR/.env" ]; then
    if [ -f "$BAK/.env" ]; then
        cp "$BAK/.env" "$DIR/.env"
        echo "    .env восстановлен из копии"
    else
        cp "$DIR/.env.example" "$DIR/.env"
        chmod 600 "$DIR/.env"
        echo
        echo "!!! ВНИМАНИЕ: создан .env из шаблона."
        echo "!!! Впишите MAX_TOKEN и AI_API_KEY:  nano $DIR/.env"
        echo "!!! Затем запустите этот скрипт ещё раз."
        exit 1
    fi
fi
chmod 600 "$DIR/.env"

echo "==> Проверяю state.json (защита от повторной публикации)"
if [ ! -f "$DIR/state.json" ] && [ -f "$BAK/state.json" ]; then
    cp "$BAK/state.json" "$DIR/state.json"
    echo "    state.json восстановлен из копии"
fi

echo "==> Обновляю зависимости"
if [ -x "$DIR/venv/bin/python" ]; then
    PY="$DIR/venv/bin/python"
elif [ -x "$DIR/.venv/bin/python" ]; then
    PY="$DIR/.venv/bin/python"
else
    PY=python3
fi
"$PY" -m pip install -q -r "$DIR/requirements.txt"

echo "==> Проверяю токен MAX (публикаций не делает)"
cd "$DIR" && "$PY" bot.py --me >/dev/null

if [ ! -f "$DIR/state.json" ]; then
    echo "==> state.json отсутствует — помечаю историю обработанной,"
    echo "    иначе бот опубликует последние посты повторно"
    "$PY" bot.py --seed
fi

echo "==> Запускаю сервис"
systemctl start "$SERVICE"
sleep 3
systemctl status "$SERVICE" --no-pager -l | head -15

echo
echo "Готово. Живой лог:  journalctl -u $SERVICE -f"
echo "Откат при проблемах:"
echo "  systemctl stop $SERVICE && rm -rf $DIR && mv $BAK $DIR && systemctl start $SERVICE"
