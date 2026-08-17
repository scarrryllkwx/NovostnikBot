@echo off
rem Запуск бота-ретранслятора MAX в режиме постоянного опроса (--loop).
rem Логи пишутся в bot.log в этой же папке.
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
py -3 bot.py --loop
pause
