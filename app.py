#!/usr/bin/env python3
"""
Instrumentarium — Desktop App Launcher
Opens a native window with the HTML UI and runs the backend server.
"""

import os, sys, threading, signal, atexit, logging, time

# ── Logging setup ──────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "instrumentarium.log")

# Logging can be disabled with INSTRUMENTARIUM_LOG=0
_LOGGING_ENABLED = os.environ.get("INSTRUMENTARIUM_LOG", "1") != "0"

if _LOGGING_ENABLED:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stderr) if sys.stderr else logging.NullHandler(),
        ],
    )
else:
    logging.basicConfig(level=logging.CRITICAL + 1)  # effectively silent

log = logging.getLogger("instrumentarium")
log.info("=== Instrumentarium starting ===")
log.info("SCRIPT_DIR: %s", SCRIPT_DIR)
log.info("sys.executable: %s", sys.executable)
log.info("sys.platform: %s", sys.platform)
if hasattr(sys, "_MEIPASS"):
    log.info("PyInstaller bundle: %s", sys._MEIPASS)

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
        log.info("Lock acquired: %s", _LOCK_PATH)
        return True
    except (ImportError, OSError, IOError) as e:
        log.warning("Could not acquire lock (another instance running?): %s", e)
        return False

if not _acquire_lock():
    log.info("Another instance is already running — exiting")
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
        log.info("Lock released")
    except Exception:
        pass

atexit.register(_cleanup_lock)

# ── Start the backend server in a background thread ─────────────────
# CRITICAL: We run server code IN-PROCESS, not via subprocess.
# When PyInstaller builds app.py, sys.executable points to the .exe itself.
# Using subprocess.Popen([sys.executable, 'server.py']) would launch another
# copy of the .exe, which launches another, creating a fork bomb.
def _start_server_in_thread():
    log.info("Starting server thread...")
    os.chdir(SCRIPT_DIR)
    try:
        import server as srv
        log.info("Server module imported successfully")

        # Run auto-setup in background
        t = threading.Thread(target=srv.run_setup, daemon=True)
        t.start()
        log.info("Auto-setup thread started")

        # Start HTTP server
        srv.srv = srv.http.server.HTTPServer(("0.0.0.0", srv.PORT), srv.Handler)
        log.info("HTTP server listening on port %d", srv.PORT)
        srv.srv.serve_forever()
    except Exception as e:
        log.error("Server thread error: %s", e, exc_info=True)

server_thread = threading.Thread(target=_start_server_in_thread, daemon=True)
server_thread.start()
log.info("Server thread launched")

# ── Open native window ─────────────────────────────────────────────
log.info("Creating webview window...")
import webview

webview.create_window(
    "🎬 Instrumentarium",
    "http://localhost:18765",
    width=620,
    height=700,
    resizable=True,
    min_size=(480, 560),
)

log.info("Starting webview main loop")
webview.start()
log.info("webview exited — shutting down")
