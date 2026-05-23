#!/usr/bin/env python3
"""
Instrumentarium — Desktop App Launcher
Opens a native window with the HTML UI and runs the backend server.
"""

import os, sys, threading, subprocess, atexit, signal

# ── Paths ──────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY  = os.path.join(SCRIPT_DIR, "server.py")

# ── Single instance lock ───────────────────────────────────────────
# Prevent multiple instances via a lock file
_LOCK_PATH = os.path.join(SCRIPT_DIR, ".instrumentarium.lock")

def _acquire_lock():
    """Create a lock file so only one instance can run."""
    global _lock_fd
    try:
        import fcntl  # Linux/macOS
        _lock_fd = open(_LOCK_PATH, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (ImportError, OSError):
        pass
    try:
        # Windows — msvcrt.locking
        import msvcrt
        _lock_fd = open(_LOCK_PATH, "w")
        msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except (ImportError, OSError):
        pass
    return True  # If locking fails silently, continue anyway

_lock_fd = None
_acquire_lock()

# ── Track the server process so we can kill it on exit ──────────────
_server_proc = None

def _kill_server():
    """Terminate the server subprocess on exit."""
    global _server_proc
    if _server_proc and _server_proc.poll() is None:
        _server_proc.terminate()
        try:
            _server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _server_proc.kill()

atexit.register(_kill_server)

# ── Start the backend server in a background thread ─────────────────
def start_server():
    global _server_proc
    import time
    _server_proc = subprocess.Popen(
        [sys.executable, SERVER_PY, "--auto-setup"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=SCRIPT_DIR,
        # Prevent the child from getting Ctrl+C meant for us
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

threading.Thread(target=start_server, daemon=True).start()

# ── Open native window ─────────────────────────────────────────────
import webview

webview.create_window(
    "🎬 Instrumentarium",
    "http://localhost:18765",
    width=620,
    height=700,
    resizable=True,
    min_size=(480, 560),
)

# Also kill server on Ctrl+C / SIGTERM
def _signal_handler(signum, frame):
    _kill_server()
    os._exit(0)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

webview.start()
