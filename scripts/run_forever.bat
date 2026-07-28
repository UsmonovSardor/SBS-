@echo off
REM ============================================================
REM  TITAN AI — 24/7 auto-restart
REM  Bot to'xtasa (crash/xato) avtomatik qayta ishga tushiradi.
REM  Windows Task Scheduler yoki startup uchun mos.
REM ============================================================
cd /d "%~dp0\.."
:loop
echo [%date% %time%] TITAN AI ishga tushmoqda...
"venv\Scripts\python.exe" main.py
echo [%date% %time%] Bot to'xtadi. 10 soniyadan keyin qayta ishga tushadi...
timeout /t 10 /nobreak >nul
goto loop
