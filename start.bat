@echo off
REM ═══════════════════════════════════════════════════════════════
REM  Video Downloader — запуск на Windows
REM  Двойной клик или start.bat в командной строке
REM ═══════════════════════════════════════════════════════════════

title Video Downloader
echo.
echo 🎬 Video Downloader
echo ═══════════════════════════════════════════════════

set "DIR=%~dp0"
set "DIR=%DIR:~0,-1%"
set "SERVER=%DIR%\server.py"
set "PORT=18765"

REM ── Check Python ────────────────────────────────────────────
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON=python" & goto :got_python
python3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON=python3" & goto :got_python

echo ❌ Python не найден. Установи Python 3.7+ и добавь в PATH:
echo    https://www.python.org/downloads/
echo    ⚠️ Поставь галочку "Add Python to PATH" при установке!
pause
exit /b 1
:got_python

REM ── Start server with auto-setup ─────────────────────────────
echo.
echo 🚀 Запуск → http://localhost:18765
echo    Для остановки: закрой это окно или нажми Ctrl+C
echo.

cd /d "%DIR%"
"%PYTHON%" "%SERVER%" --auto-setup

pause
