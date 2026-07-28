@echo off
REM ============================================================
REM  TITAN AI — botni bir marta ishga tushiradi
REM ============================================================
cd /d "%~dp0\.."
echo TITAN AI ishga tushmoqda...
echo Loyiha: %CD%
echo To'xtatish: Ctrl+C
echo ============================================================
"venv\Scripts\python.exe" main.py
pause
