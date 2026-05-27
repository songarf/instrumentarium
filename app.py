#!/usr/bin/env python3
"""
Instrumentarium — Desktop App Launcher
Opens a native window with the HTML UI and runs the backend server.
"""

import os, sys, threading, signal, atexit, logging, time

# ── Detach from console on Windows (must be done before anything else) ──
if sys.platform == "win32" and not sys.stdout:
    # PyInstaller console=False sets stdout/stderr to None.
    # Explicitly redirect to devnull to prevent any module from reopening stdout.
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

# ── Working directory ───────────────────────────────────────────────
# All working files (logs, .bin, downloads, .setup_done, lock) go beside
# the .exe / script — single folder, no scattering across the system.
if hasattr(sys, "_MEIPASS"):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(_BASE_DIR, exist_ok=True)

# ── Logging ──────────────────────────────────────────────────────────
_LOG_HANDLERS = []
try:
    _LOG_HANDLERS.append(logging.FileHandler(os.path.join(_BASE_DIR, "instrumentarium.log"), encoding="utf-8"))
except Exception:
    pass
if not _LOG_HANDLERS:
    try:
        _LOG_HANDLERS.append(logging.FileHandler("instrumentarium.log", encoding="utf-8"))
    except Exception:
        pass

# Logging can be disabled with INSTRUMENTARIUM_LOG=0
_LOGGING_ENABLED = os.environ.get("INSTRUMENTARIUM_LOG", "1") != "0"

if _LOGGING_ENABLED and _LOG_HANDLERS:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=_LOG_HANDLERS,
    )
elif not _LOGGING_ENABLED:
    logging.basicConfig(level=logging.CRITICAL + 1)

log = logging.getLogger("instrumentarium")
log.info("=== Instrumentarium starting ===")
log.info("BASE_DIR: %s", _BASE_DIR)
log.info("sys.executable: %s", sys.executable)
log.info("sys.platform: %s", sys.platform)
if hasattr(sys, "_MEIPASS"):
    log.info("PyInstaller bundle: %s", sys._MEIPASS)

# ── Single instance lock ───────────────────────────────────────────
_LOCK_PATH = os.path.join(_BASE_DIR, ".instrumentarium.lock")
_SETUP_MARKER_PATH = os.path.join(_BASE_DIR, ".setup_done")
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
    log.info("_cleanup_lock: running")
    if _lock_fd:
        try:
            _lock_fd.close()
            log.info("_cleanup_lock: lock fd closed")
        except Exception as e:
            log.warning("_cleanup_lock: error closing lock fd: %s", e)
    try:
        os.remove(_LOCK_PATH)
        log.info("_cleanup_lock: lock file removed: %s", _LOCK_PATH)
    except Exception:
        log.info("_cleanup_lock: lock file already gone or not removable")

atexit.register(_cleanup_lock)
log.info("atexit handler registered: _cleanup_lock")

# ── Start the backend server in a background thread ─────────────────
# CRITICAL: We run server code IN-PROCESS, not via subprocess.
# When PyInstaller builds app.py, sys.executable points to the .exe itself.
# Using subprocess.Popen([sys.executable, 'server.py']) would launch another
# copy of the .exe, which launches another, creating a fork bomb.

SETUP_MARKER_PATH = _SETUP_MARKER_PATH

def _start_server_in_thread():
    log.info("=== Server thread starting ===")
    log.info("_BASE_DIR: %s", _BASE_DIR)
    log.info("_SETUP_MARKER_PATH: %s", _SETUP_MARKER_PATH)
    os.chdir(_BASE_DIR)
    log.info("CWD after chdir: %s", os.getcwd())
    try:
        import server as srv
        log.info("server.SCRIPT_DIR: %s", srv.SCRIPT_DIR)
        log.info("server.SETUP_MARKER: %s", srv.SETUP_MARKER)
        log.info("server._BASE_DIR: %s", srv._BASE_DIR)

        marker_exists = os.path.exists(_SETUP_MARKER_PATH)
        log.info(".setup_done exists: %s", marker_exists)

        if marker_exists:
            srv.setup_state["phase"] = "silent_check"
            srv.setup_state["setup_done"] = True
            log.info("Starting silent dep check thread...")
            t = threading.Thread(target=srv._ensure_deps, daemon=True)
            t.start()
        else:
            log.info("Starting full setup wizard thread...")
            t = threading.Thread(target=srv.run_setup, daemon=True)
            t.start()

        log.info("Creating HTTP server on 0.0.0.0:%d...", 18765)
        srv.srv = srv.http.server.HTTPServer(("0.0.0.0", srv.PORT), srv.Handler)
        srv.srv.allow_reuse_address = True
        srv.srv.timeout = 0.5
        log.info("HTTP server created, calling serve_forever()...")
        srv.srv.serve_forever()
        log.info("serve_forever() returned — server thread exiting")
    except Exception as e:
        log.error("Server thread error: %s", e, exc_info=True)

log.info("Launching server thread...")
server_thread = threading.Thread(target=_start_server_in_thread, daemon=True)
server_thread.start()
log.info("Server thread launched, id=%d", server_thread.ident)

# Wait until server is actually listening (max 5s)
import socket
for _ in range(50):
    try:
        sock = socket.create_connection(("127.0.0.1", 18765), timeout=0.1)
        sock.close()
        log.info("Server is ready on port 18765")
        break
    except (ConnectionRefusedError, OSError):
        time.sleep(0.1)
else:
    log.warning("Server didn't start in time, proceeding anyway")

# ── Open UI in a native app window (pywebview) ─────────────────────
log.info("Opening window...")

def _do_cleanup() -> None:
    """Kill yt-dlp subprocess, stop server, remove lock file."""
    log.info("_do_cleanup: running")
    try:
        import urllib.request as _ur
        _ur.urlopen("http://127.0.0.1:18765/shutdown", timeout=5)
        log.info("_do_cleanup: /shutdown sent successfully")
    except Exception as e:
        log.warning("_do_cleanup: could not send /shutdown: %s", e)
    _cleanup_lock()


def _do_cleanup_async() -> None:
    """Run _do_cleanup in a daemon thread so the window can close immediately."""
    t = threading.Thread(target=_do_cleanup, daemon=True)
    t.start()

try:
    import webview

    window = webview.create_window(
        "Instrumentarium",
        url="http://localhost:18765",
        width=620,
        height=720,
        resizable=False,
    )

    if window:
        def _on_closing():
            log.info("=== Window close event received ===")
            _do_cleanup_async()
            log.info("=== Final exit ===")
            os._exit(0)

        window.events.closing += _on_closing

    # Also handle SIGTERM (e.g. from xdotool windowclose or kill)
    import signal as _signal
    def _sigterm_handler(signum, frame):
        log.info("=== SIGTERM received ===")
        _do_cleanup_async()
        log.info("=== Final exit ===")
        os._exit(0)
    _signal.signal(_signal.SIGTERM, _sigterm_handler)

    # Try renderers in order of preference:
    #   1. edgechromium (WebView2, modern Chromium — needs WebView2 Runtime)
    #   2. default auto-detect (GTK/Qt/Cocoa depending on platform)
    _renderers = ["edgechromium"] if sys.platform == "win32" else []
    _started = False
    for _gui in _renderers:
        try:
            log.info("Trying webview gui=%s ...", _gui)
            webview.start(gui=_gui)
            log.info("webview.start(gui=%s) returned — window closed", _gui)
            _started = True
            break
        except Exception as _e:
            log.warning("webview gui=%s failed: %s", _gui, _e)

    if not _started:
        log.info("Falling back to webview auto-detect")
        webview.start()
        log.info("webview.start() returned — window closed")

    log.info("=== pywebview event loop exited ===")

except Exception as e:
    log.error("Could not open native window: %s", e, exc_info=True)
    import webbrowser, threading
    webbrowser.open("http://localhost:18765")
    log.info("Opened in system browser — blocking main thread")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    log.info("Main thread unblocked — exiting")

# Cleanup lock file — must be done here, not in atexit, because
# pywebview/GTK may call exit() internally and skip atexit handlers.
_cleanup_lock()
log.info("=== Instrumentarium shutdown complete ===")
