#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Video Downloader — запуск на Linux / macOS / WSL
#  Двойной клик или: bash start.sh
# ═══════════════════════════════════════════════════════════════

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="$DIR/server.py"
PORT=18765

echo ""
echo "🎬 Video Downloader"
echo "═══════════════════════════════════════════"

# ── Check Python ──────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "❌ Python не найден. Установи Python 3.7+:"
    echo "   https://www.python.org/downloads/"
    echo ""
    echo "   Ubuntu/Debian:  sudo apt install python3"
    echo "   Fedora:         sudo dnf install python3"
    echo "   Arch:           sudo pacman -S python"
    echo "   macOS:          brew install python3"
    exit 1
fi
echo "✅ Python: $($PYTHON --version)"

# ── Kill previous instance ────────────────────────────────────
if command -v lsof &>/dev/null; then
    PID=$(lsof -ti tcp:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "⚠️  Порт $PORT занят (PID $PID), освобождаю…"
        kill "$PID" 2>/dev/null || true
        sleep 1
    fi
fi

# ── Start server with auto-setup ───────────────────────────────
echo ""
echo "🚀 Запуск → http://localhost:$PORT"
echo "   Для остановки: Ctrl+C"
echo ""

$PYTHON "$SERVER" --auto-setup
