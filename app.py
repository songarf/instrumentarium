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

# ── Logging setup ──────────────────────────────────────────────────
# When running from PyInstaller bundle, __file__ points to temp _MEI dir.
# Use sys.executable location for persistent log file.
if hasattr(sys, "_MEIPASS"):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_PATH = os.path.join(_BASE_DIR, "instrumentarium.log")

# Logging can be disabled with INSTRUMENTARIUM_LOG=0
_LOGGING_ENABLED = os.environ.get("INSTRUMENTARIUM_LOG", "1") != "0"

if _LOGGING_ENABLED:
    # File only — no StreamHandler to avoid creating a console window
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
        ],
    )
else:
    logging.basicConfig(level=logging.CRITICAL + 1)  # effectively silent

log = logging.getLogger("instrumentarium")
log.info("=== Instrumentarium starting ===")
log.info("BASE_DIR: %s", _BASE_DIR)
log.info("sys.executable: %s", sys.executable)
log.info("sys.platform: %s", sys.platform)
if hasattr(sys, "_MEIPASS"):
    log.info("PyInstaller bundle: %s", sys._MEIPASS)

# ── Single instance lock ───────────────────────────────────────────
# Use %LOCALAPPDATA%\Instrumentarium for lock file (same as server.py)
if sys.platform == "win32":
    _PERSIST_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Instrumentarium")
else:
    _PERSIST_DIR = os.path.join(os.environ.get("HOME", ""), ".instrumentarium")
os.makedirs(_PERSIST_DIR, exist_ok=True)

_LOCK_PATH = os.path.join(_PERSIST_DIR, ".instrumentarium.lock")
_SETUP_MARKER_PATH = os.path.join(_PERSIST_DIR, ".setup_done")
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

SETUP_MARKER_PATH = _SETUP_MARKER_PATH

def _start_server_in_thread():
    log.info("Starting server thread...")
    log.info("_BASE_DIR: %s", _BASE_DIR)
    log.info("_SETUP_MARKER_PATH: %s", _SETUP_MARKER_PATH)
    os.chdir(_BASE_DIR)
    try:
        import server as srv
        log.info("Server module imported successfully")
        log.info("server.SCRIPT_DIR: %s", srv.SCRIPT_DIR)
        log.info("server.SETUP_MARKER: %s", srv.SETUP_MARKER)

        marker_exists = os.path.exists(_SETUP_MARKER_PATH)
        log.info("Setup marker exists: %s", marker_exists)

        if marker_exists:
            # Already configured — just do a silent dep check, no UI needed
            log.info("Previous setup found — running silent dep check...")
            t = threading.Thread(target=srv._ensure_deps, daemon=True)
            t.start()
        else:
            # First launch — run the full visible setup wizard
            log.info("No setup marker — starting full setup wizard...")
            t = threading.Thread(target=srv.run_setup, daemon=True)
            t.start()
        log.info("Dep-check/setup thread started")

        # Start HTTP server
        srv.srv = srv.http.server.HTTPServer(("0.0.0.0", srv.PORT), srv.Handler)
        log.info("HTTP server listening on port %d", srv.PORT)
        srv.srv.serve_forever()
    except Exception as e:
        log.error("Server thread error: %s", e, exc_info=True)

server_thread = threading.Thread(target=_start_server_in_thread, daemon=True)
server_thread.start()
log.info("Server thread launched")

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

# ── Open UI in app window (pywebview) with browser fallback ──────────
log.info("Opening window...")
try:
    import webview
    
    # Check if WebView2 Runtime is available on Windows
    _webview2_available = False
    if sys.platform == "win32":
        try:
            import winreg
            # Check registry for WebView2 Evergreen Runtime
            key_path = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                val, _ = winreg.QueryValueEx(key, "pv")
                winreg.CloseKey(key)
                if val and val != "0.0.0.0":
                    _webview2_available = True
                    log.info("WebView2 Runtime found: %s", val)
            except FileNotFoundError:
                # Try 32-bit registry
                try:
                    key_path32 = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path32)
                    val, _ = winreg.QueryValueEx(key, "pv")
                    winreg.CloseKey(key)
                    if val and val != "0.0.0.0":
                        _webview2_available = True
                        log.info("WebView2 Runtime found: %s", val)
                except FileNotFoundError:
                    log.info("WebView2 Runtime not found in registry")
        except Exception as e:
            log.info("Could not check WebView2 registry: %s", e)
    
    if _webview2_available:
        # Use native WebView2 window
        log.info("Using WebView2 for native window")
        webview.create_window(
            "Instrumentarium",
            url="http://localhost:18765",
            width=620,
            height=700,
            resizable=True,
            min_size=(540, 500),
        )
        webview.start(gui="edgechromium")
    else:
        # Fallback: open in default browser
        log.info("WebView2 not available, falling back to system browser")
        raise ImportError("WebView2 not available")
        
except Exception as e:
    if "import" in str(e).lower() or "WebView2" in str(e):
        log.info("pywebview/WebView2 not available, using webbrowser fallback: %s", e)
    import webbrowser
    webbrowser.open("http://localhost:18765")
    log.info("Browser opened — keeping server alive")
    # Keep the process alive so the server keeps running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
