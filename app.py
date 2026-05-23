#!/usr/bin/env python3
"""
Instrumentarium — Desktop App Launcher
Opens a native window with the HTML UI and runs the backend server.
"""

import os, sys, threading, signal, atexit

# ── Paths ──────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Single instance lock ───────────────────────────────────────────
_LOCK_PATH = os.path.join(SCRIPT_DIR, ".instrumentarium.lock")
_lock_fd = None

def _acquire_lock():
    """Try to acquire a lock file. Returns True if lock acquired."""
    global _lock_fd
    try:
        if sys.platform == "win32":
            import msvcrt
            _lock_fd = open(_LOCK_PATH, "w")
            msvcrt.locking(_lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            _lock_fd = open(_LOCK_PATH, "w")
            fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (ImportError, OSError, IOError):
        return False

if not _acquire_lock():
    # Another instance is already running — exit silently
    sys.exit(0)

def _cleanup_lock():
    global _lock_fd
    if _lock_fd:
        try:
            _lock_fd.close()
        except Exception:
            pass
    try:
        os.remove(_LOCK_PATH)
    except Exception:
        pass

atexit.register(_cleanup_lock)

# ── Start the backend server in a background thread ─────────────────
# CRITICAL: We run server code IN-PROCESS, not via subprocess.
# When PyInstaller builds app.py, sys.executable points to the .exe itself.
# Using subprocess.Popen([sys.executable, 'server.py']) would launch another
# copy of the .exe, which launches another, creating a fork bomb.
def _start_server_in_thread():
    os.chdir(SCRIPT_DIR)
    import server as srv

    # Run auto-setup in background
    t = threading.Thread(target=srv.run_setup, daemon=True)
    t.start()

    # Start HTTP server
    srv.srv = srv.http.server.HTTPServer(("0.0.0.0", srv.PORT), srv.Handler)
    try:
        srv.srv.serve_forever()
    except Exception:
        pass

threading.Thread(target=_start_server_in_thread, daemon=True).start()

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

webview.start()
