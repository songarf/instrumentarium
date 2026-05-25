#!/usr/bin/env python3
"""
Instrumentarium — Setup Wizard + Server
Checks dependencies, installs yt-dlp, starts the server, opens browser.
"""

import http.server, json, logging, os, platform, shutil, ssl, subprocess, sys, threading, time, urllib.request, uuid, zipfile
from urllib.parse import urlparse, parse_qs

# ── Logging ──────────────────────────────────────────────────────────
log = logging.getLogger("instrumentarium.server")

def _wait_deps(handler, timeout=30):
    """Wait for silent dep check to complete, then respond."""
    import time as _t
    _deadline = _t.time() + timeout
    while _t.time() < _deadline:
        if setup_state["phase"] == "done":
            # Re-process the download request now that deps are ready
            handler._json({"ok": True, "deps_ready": True})
            return
        if setup_state["phase"] == "error":
            handler._json({"error": "Setup failed: " + str(setup_state.get("error", "unknown"))})
            return
        _t.sleep(0.5)
    handler._json({"error": "Timeout waiting for dependencies"})

def _ensure_log_handler():
    """Make sure the server logger has at least one handler.
    When run from app.py, basicConfig already set up a root FileHandler
    that this logger inherits. When run standalone, add our own."""
    if not log.handlers and not logging.getLogger().handlers:
        # Use same logic as app.py for base directory
        if hasattr(sys, "_MEIPASS"):
            _base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            _base = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(_base, exist_ok=True)
        _log_path = os.path.join(_base, "instrumentarium.log")
        _fh = logging.FileHandler(_log_path, encoding="utf-8")
        _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(_fh)

_ensure_log_handler()

def _safe_print(*args, **kwargs):
    """Print safely — skip when stdout is None (PyInstaller console=False on Windows)."""
    if sys.stdout:
        try:
            print(*args, **kwargs)
        except Exception:
            pass



# ── Config ──────────────────────────────────────────────────────────
PORT = 18765

# ── Working directory ───────────────────────────────────────────────
# All working files (logs, .bin, downloads, .setup_done, lock) go beside
# the .exe / script — single folder, no scattering across the system.
if hasattr(sys, "_MEIPASS"):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(_BASE_DIR, exist_ok=True)

SETUP_MARKER = os.path.join(_BASE_DIR, ".setup_done")
_LOCK_PATH = os.path.join(_BASE_DIR, ".instrumentarium.lock")

# When running from PyInstaller, __file__ points to temp _MEI dir.
# Use sys.executable location for runtime data (downloads, .bin).
if hasattr(sys, "_MEIPASS"):
    _EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    SCRIPT_DIR = _EXE_DIR
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_BASE = os.path.join(_BASE_DIR, "downloads")

# yt-dlp binary locations — all beside the exe
if hasattr(sys, "_MEIPASS"):
    _BIN_CANDIDATES = [
        os.path.join(_BASE_DIR, ".bin"),
        os.path.join(_EXE_DIR, ".bin"),
        os.path.join(sys._MEIPASS, ".bin"),
    ]
else:
    _BIN_CANDIDATES = [os.path.join(SCRIPT_DIR, ".bin")]

YT_DLP_DIR = _BIN_CANDIDATES[0]
YT_DLP = os.path.join(YT_DLP_DIR, "yt-dlp.exe" if platform.system() == "Windows" else "yt-dlp")

# ── Subprocess helper — no console windows on Windows ───────────────
def _popen(cmd, **kwargs):
    """subprocess.Popen that never flashes a console window on Windows."""
    if platform.system() == "Windows":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.STDOUT)
    kwargs.setdefault("text", True)
    # Do NOT set bufsize=1 — line-buffered text mode can deadlock with
    # stderr redirected to stdout. Use default buffering and read all at once.
    return subprocess.Popen(cmd, **kwargs)

# ── Setup state (shared with HTTP handler) ──────────────────────────
setup_state = {
    "phase": "idle",        # idle | checking | silent_check | installing_python | installing_ytdlp | done | error
    "progress": 0,          # 0-100
    "messages": [],         # list of {text, type}
    "python_ok": False,
    "ytdlp_ok": False,
    "server_started": False,
    "error": None,
    "setup_done": False,    # True if .setup_done marker exists
}

def msg(text, type="info"):
    setup_state["messages"].append({"text": text, "type": type, "time": time.time()})

# ── Dependency checks ───────────────────────────────────────────────
def find_system_python():
    """Find any usable Python 3.7+ on the system."""
    candidates = ["python3", "python", "py"]
    if platform.system() == "Windows":
        candidates = ["py", "python", "python3"]
    for c in candidates:
        p = shutil.which(c)
        if p:
            try:
                out = subprocess.check_output([p, "--version"], stderr=subprocess.STDOUT, text=True,
                                             creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0).strip()
                # Parse version
                parts = out.split()
                if len(parts) >= 2:
                    ver = parts[1].split(".")
                    major, minor = int(ver[0]), int(ver[1])
                    if major >= 3 and (major > 3 or minor >= 7):
                        return p, out
            except:
                continue
    return None, None

def check_ytdlp():
    """Check if yt-dlp exists in any known location."""
    # Check all bin candidates (beside exe first, then bundle)
    for d in _BIN_CANDIDATES:
        candidate = os.path.join(d, "yt-dlp.exe" if platform.system() == "Windows" else "yt-dlp")
        log.info("check_ytdlp: trying %s (exists=%s)", candidate, os.path.isfile(candidate))
        if os.path.isfile(candidate):
            try:
                out = subprocess.check_output([candidate, "--version"], stderr=subprocess.STDOUT, text=True,
                                             creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0).strip()
                log.info("check_ytdlp: found %s version=%s", candidate, out)
                return True, out
            except Exception as e:
                log.info("check_ytdlp: %s exists but --version failed: %s", candidate, e)
    # Also check system PATH
    sys_yt = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if sys_yt:
        try:
            out = subprocess.check_output([sys_yt, "--version"], stderr=subprocess.STDOUT, text=True,
                                         creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0).strip()
            return True, out
        except:
            pass
    log.info("check_ytdlp: not found in any location")
    return False, None

def install_ytdlp():
    """Download yt-dlp into .bin/."""
    os.makedirs(YT_DLP_DIR, exist_ok=True)
    is_win = platform.system() == "Windows"

    # Multiple URLs to try (GitHub + mirrors)
    if is_win:
        urls = [
            "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
            "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
        ]
    else:
        urls = [
            "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
        ]

    setup_state["phase"] = "installing_ytdlp"
    msg(f"⬇️  Скачиваю yt-dlp…", "info")
    log.info("Downloading yt-dlp, trying %d URLs", len(urls))
    setup_state["progress"] = 50

    for url in urls:
        log.info("Trying: %s", url)
        try:
            # Use curl for better proxy/redirect support
            if shutil.which("curl"):
                cmd = ["curl", "-L", "-f", "--connect-timeout", "15", "--max-time", "120",
                       "-o", YT_DLP, url]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=130,
                                       creationflags=subprocess.CREATE_NO_WINDOW if is_win else 0)
                if result.returncode != 0:
                    log.warning("curl failed (%d): %s", result.returncode, result.stderr[:200])
                    continue
            else:
                # Fallback to urllib
                urllib.request.urlretrieve(url, YT_DLP)

            if not is_win:
                os.chmod(YT_DLP, 0o755)

            ver = subprocess.check_output([YT_DLP, "--version"], stderr=subprocess.STDOUT, text=True,
                                         creationflags=subprocess.CREATE_NO_WINDOW if is_win else 0).strip()
            msg(f"✅ yt-dlp {ver} установлен", "ok")
            log.info("yt-dlp %s installed at %s", ver, YT_DLP)
            setup_state["progress"] = 70
            return True
        except Exception as e:
            log.warning("Failed to download from %s: %s", url, e)
            continue

    msg(f"❌ Ошибка загрузки yt-dlp: все источники недоступны", "err")
    log.error("yt-dlp installation failed from all URLs")
    setup_state["error"] = "yt-dlp download failed (502/503/timeout)"
    setup_state["phase"] = "error"
    return False

def get_python_install_url():
    """Return the official Python download URL for current OS."""
    system = platform.system()
    arch = platform.machine().lower()
    if system == "Windows":
        if "64" in arch or arch == "amd64":
            return "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
        return "https://www.python.org/ftp/python/3.12.9/python-3.12.9.exe"
    elif system == "Darwin":
        return "https://www.python.org/ftp/python/3.12.9/python-3.12.9-macos11.pkg"
    else:
        return None  # Linux — use package manager

def install_python():
    """Download and install Python on Windows. On Linux/Mac, show instructions."""
    system = platform.system()
    setup_state["phase"] = "installing_python"

    if system == "Linux":
        msg("🐧 Установи Python через пакетный менеджер:", "info")
        msg("   Ubuntu/Debian: sudo apt install python3", "info")
        msg("   Fedora:        sudo dnf install python3", "info")
        msg("   Arch:          sudo pacman -S python", "info")
        msg("   Затем перезапусти start.sh", "info")
        setup_state["phase"] = "error"
        setup_state["error"] = "Python not installed"
        return False

    if system == "Darwin":
        msg("🍎 Установи Python:", "info")
        msg("   brew install python3", "info")
        msg("   Или: https://www.python.org/downloads/macos/", "info")
        setup_state["phase"] = "error"
        setup_state["error"] = "Python not installed"
        return False

    # Windows — auto-install
    url = get_python_install_url()
    if not url:
        msg("❌ Не удалось определить ссылку для скачивания Python", "err")
        log.error("Could not determine Python download URL for %s", system)
        setup_state["phase"] = "error"
        return False

    installer_path = os.path.join(SCRIPT_DIR, "python_installer.exe")
    msg(f"⬇️  Скачиваю Python 3.12… (~25 MB)", "info")
    log.info("Downloading Python 3.12 from %s", url)
    setup_state["progress"] = 10

    try:
        def reporthook(block_num, block_size, total_size):
            if total_size > 0:
                pct = min(int(block_num * block_size * 40 / total_size), 40)
                setup_state["progress"] = 10 + pct

        urllib.request.urlretrieve(url, installer_path, reporthook)
        msg("✅ Python скачен. Запускаю установщик…", "ok")
        log.info("Python installer downloaded, running setup…")
        setup_state["progress"] = 55
        setup_state["phase"] = "installing_python"

        # Run installer silently with PATH addition
        subprocess.check_call([
            installer_path,
            "/quiet", "InstallAllUsers=0",
            "PrependPath=1",
            "Include_pip=1",
        ])
        msg("✅ Python установлен! Перезапусти приложение вручную.", "ok")
        log.info("Python installed successfully — user should relaunch")
        setup_state["progress"] = 100
        setup_state["phase"] = "done"
        setup_state["python_ok"] = True
        setup_state["server_started"] = True
        # Do NOT os.execv — let the user relaunch manually

    except Exception as e:
        msg(f"❌ Ошибка установки Python: {e}", "err")
        msg(f"   Скачай вручную: {url}", "info")
        log.error("Python installation failed: %s", e)
        setup_state["phase"] = "error"
        setup_state["error"] = str(e)
        return False

def _find_ffmpeg():
    """Look for ffmpeg binary near the exe or in PATH. Returns path or None."""
    if platform.system() == "Windows":
        names = ["ffmpeg.exe", "ffmpeg"]
    else:
        names = ["ffmpeg"]
    # Check all bin candidates
    for d in _BIN_CANDIDATES:
        for name in names:
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return candidate
    # Check system PATH
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")

def _has_ffmpeg():
    """Return True if ffmpeg is available."""
    return _find_ffmpeg() is not None
def _write_marker():
    """Write .setup_done marker file."""
    try:
        log.info("Writing setup marker to: %s", SETUP_MARKER)
        with open(SETUP_MARKER, "w") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
        log.info("Setup marker written successfully")
    except Exception as e:
        log.error("Could not write setup marker to %s: %s", SETUP_MARKER, e)

def _clear_marker():
    """Remove .setup_done marker file."""
    try:
        if os.path.exists(SETUP_MARKER):
            log.info("Removing setup marker: %s", SETUP_MARKER)
            os.remove(SETUP_MARKER)
    except Exception as e:
        log.error("Could not remove setup marker: %s", e)

def _ensure_deps():
    """Silent dependency check — no messages, no UI."""
    log.info("_ensure_deps: starting silent dep check")
    try:
        py_path, _ = find_system_python()
        if not py_path:
            log.warning("_ensure_deps: Python not found, setup needed")
            return False
        log.info("_ensure_deps: Python found: %s", py_path)

        ok, ver = check_ytdlp()
        if not ok:
            log.info("_ensure_deps: yt-dlp not found, downloading...")
            if not install_ytdlp():
                log.error("_ensure_deps: yt-dlp download failed")
                return False
        else:
            log.info("_ensure_deps: yt-dlp found: %s", ver)

        os.makedirs(OUTPUT_BASE, exist_ok=True)
        setup_state["python_ok"] = True
        setup_state["ytdlp_ok"] = True
        setup_state["phase"] = "done"
        setup_state["progress"] = 100
        setup_state["server_started"] = True
        _write_marker()
        log.info("_ensure_deps: all deps OK, phase=done")
        return True
    except Exception as e:
        log.error("_ensure_deps: exception: %s", e, exc_info=True)
        return False

def run_setup():
    """Full visible setup: check Python → check/install ytdlp → start server."""
    log.info("run_setup: starting full setup wizard")
    setup_state["progress"] = 0
    setup_state["messages"] = []
    setup_state["error"] = None
    _clear_marker()

    log.info("Setup started")
    msg("🔍 Проверяю зависимости…", "info")
    setup_state["progress"] = 5

    # ── Step 1: Python ───────────────────────────────────────────
    py_path, py_ver = find_system_python()
    if py_path:
        log.info("Python found: %s (%s)", py_path, py_ver)
        msg(f"✅ {py_ver} найден: {py_path}", "ok")
        setup_state["python_ok"] = True
        setup_state["progress"] = 30
    else:
        log.warning("Python 3.7+ not found")
        msg("❌ Python 3.7+ не найден", "err")
        setup_state["python_ok"] = False
        if not install_python():
            log.error("Python installation failed or not available")
            return

    # ── Step 2: yt-dlp ───────────────────────────────────────────
    ok, ver = check_ytdlp()
    if ok:
        log.info("yt-dlp found: %s", ver)
        msg(f"✅ yt-dlp {ver} найден", "ok")
        setup_state["ytdlp_ok"] = True
        setup_state["progress"] = 70
    else:
        log.info("yt-dlp not found, downloading...")
        msg("⚠️  yt-dlp не найден, скачиваю…", "info")
        if not install_ytdlp():
            log.error("yt-dlp installation failed")
            return

    # ── Step 3: Ready ────────────────────────────────────────────
    setup_state["progress"] = 90
    log.info("Creating downloads directory: %s", OUTPUT_BASE)
    msg("📁 Создаю папку для загрузок…", "info")
    os.makedirs(OUTPUT_BASE, exist_ok=True)
    msg(f"✅ Готово! Запускаю сервер на порту {PORT}…", "ok")
    setup_state["progress"] = 100
    setup_state["phase"] = "done"
    setup_state["server_started"] = True
    _write_marker()
    log.info("Setup complete — server ready on port %d", PORT)

# ── HTTP handler ────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urlparse(self.path)

        if p.path in ("/", "/index.html"):
            _serve_html_file(self)
            return

        if p.path == "/open-folder":
            import subprocess as _sp, subprocess
            folder = os.path.abspath(OUTPUT_BASE)
            log.info("/open-folder: %s", folder)
            if platform.system() == "Windows":
                _sp.Popen(["explorer", folder], creationflags=subprocess.CREATE_NO_WINDOW)
            elif platform.system() == "Darwin":
                _sp.Popen(["open", folder])
            else:
                _sp.Popen(["xdg-open", folder])
            self._json({"ok": True})
            return

        if p.path == "/status":
            # On first contact, check if setup was already done
            if setup_state["phase"] == "idle" and os.path.exists(SETUP_MARKER):
                # Run dep check in background thread to avoid blocking HTTP response
                setup_state["phase"] = "silent_check"
                t = threading.Thread(target=_ensure_deps, daemon=True)
                t.start()
                setup_state["setup_done"] = True
            elif setup_state["phase"] == "idle":
                setup_state["setup_done"] = False
            resp = {
                "phase": setup_state["phase"],
                "progress": setup_state["progress"],
                "messages": setup_state["messages"],
                "python_ok": setup_state["python_ok"],
                "ytdlp_ok": setup_state["ytdlp_ok"],
                "server_started": setup_state["server_started"],
                "error": setup_state["error"],
                "setup_done": os.path.exists(SETUP_MARKER),
            }
            log.info("/status: phase=%s setup_done=%s marker_exists=%s", setup_state["phase"], resp["setup_done"], os.path.exists(SETUP_MARKER))
            self._json(resp)
            return

        if p.path == "/log":
            qs = parse_qs(p.query)
            jid = qs.get("job", [""])[0]
            off = int(qs.get("offset", ["0"])[0])
            j = download_jobs.get(jid)
            if not j:
                self._json({"error": "Job not found", "status": "error"})
                return
            self._json({"lines": j["log"][off:], "status": j["status"]})
            return

        self.send_error(404)

    def do_POST(self):
        if self.path == "/setup":
            # If already done, just confirm
            if setup_state["phase"] == "done" and os.path.exists(SETUP_MARKER):
                self._json({"ok": True, "already_done": True})
                return
            # Start fresh setup in background thread
            if setup_state["phase"] in ("idle", "error", "done"):
                t = threading.Thread(target=run_setup, daemon=True)
                t.start()
            self._json({"ok": True})
            return

        if self.path == "/download":
            log.info("/download: phase=%s, url_body_pending", setup_state["phase"])
            if setup_state["phase"] == "error":
                err = setup_state.get("error", "unknown")
                log.warning("/download: setup in error state: %s", err)
                self._json({"error": "Setup failed: " + str(err)})
                return
            if setup_state["phase"] not in ("done", "silent_check"):
                log.warning("/download: setup not complete, phase=%s", setup_state["phase"])
                self._json({"error": "Setup not complete"})
                return
            # Wait for silent dep check to finish if it's still running
            if setup_state["phase"] == "silent_check":
                log.info("/download: waiting for silent dep check (timeout=30s)...")
                _wait_deps(self)
                return
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            url = body.get("url", "").strip()
            mode = body.get("mode", "video")
            log.info("/download: url=%s mode=%s", url, mode)
            if not url:
                self._json({"error": "URL is required"})
                return
            jid = str(uuid.uuid4())[:8]
            download_jobs[jid] = {"log": [], "status": "running"}
            # Find yt-dlp: check all candidates, then system PATH
            yt = None
            for d in _BIN_CANDIDATES:
                candidate = os.path.join(d, "yt-dlp.exe" if platform.system() == "Windows" else "yt-dlp")
                if os.path.isfile(candidate):
                    yt = candidate
                    break
            if not yt:
                yt = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe") or "yt-dlp"
            log.info("/download: yt-dlp resolved to: %s (exists=%s)", yt, os.path.isfile(yt))
            JobLogger(jid, url, mode, yt).start()
            log.info("/download: job started, job_id=%s", jid)
            self._json({"job_id": jid, "platform": detect_platform(url)})
            return

        if self.path == "/shutdown":
            log.info("/shutdown received — killing active subprocesses and stopping server")
            proc = _active_proc[0]
            if proc and proc.poll() is None:
                log.info("/shutdown: killing active yt-dlp pid=%d", proc.pid)
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
            _active_proc[0] = None
            # Schedule server shutdown in a background thread (can't block this one)
            import threading as _th
            _th.Thread(target=lambda: (time.sleep(0.2), srv.shutdown()), daemon=True).start()
            self._json({"ok": True})
            return

        self.send_error(404)

    def log_message(self, format, *args):
        """Override default stderr logging — write to our log file instead."""
        log.debug("HTTP %s %s", self.command, self.path)

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

# ── Serve UI ────────────────────────────────────────────────────────
# Strategy: in PyInstaller one-file mode, datas files are extracted to
# _MEIPASS temp folder. But CI may not include them. So we try:
#   1. Explicit path beside the .exe (_EXE_DIR/download.html)
#   2. PyInstaller _MEIPA SS temp folder
#   3. Same dir as __file__ (dev mode)

_HTML_CANDIDATES = []

if hasattr(sys, "_MEIPASS"):
    _HTML_CANDIDATES.append(os.path.join(sys._MEIPASS, "download.html"))

# Always check beside the exe/app bundle (covers CI case)
_HTML_CANDIDATES.append(os.path.join(SCRIPT_DIR, "download.html"))

# Also check exe dir explicitly
if hasattr(sys, "_MEIPASS"):
    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    _HTML_CANDIDATES.append(os.path.join(_exe_dir, "download.html"))


def _serve_html_file(handler):
    """Serve the HTML UI — search multiple locations."""
    html = None
    for path in _HTML_CANDIDATES:
        try:
            with open(path, "r", encoding="utf-8") as f:
                html = f.read()
            log.info("Serving HTML from: %s", path)
            break
        except FileNotFoundError:
            continue
    if html is None:
        html = "<h1>UI file not found</h1><p>Tried: " + ", ".join(_HTML_CANDIDATES) + "</p>"
        log.error("download.html not found in any location: %s", _HTML_CANDIDATES)
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

# ── Download job logger ─────────────────────────────────────────────
download_jobs = {}
_active_proc = [None]  # Currently running yt-dlp subprocess (list for mutability without global)

def detect_platform(url):
    u = url.lower()
    for name, domains in [
        ("youtube", ["youtube.com", "youtu.be"]),
        ("twitter", ["twitter.com", "x.com"]),
        ("tiktok", ["tiktok.com"]),
        ("instagram", ["instagram.com"]),
        ("facebook", ["facebook.com", "fb.com", "fb.watch"]),
        ("linkedin", ["linkedin.com"]),
    ]:
        for d in domains:
            if d in u:
                return name
    return "other"

class JobLogger(threading.Thread):
    def __init__(self, job_id, url, mode, yt_dlp_path):
        super().__init__(daemon=True)
        self.job_id = job_id
        self.url = url
        self.mode = mode
        self.yt = yt_dlp_path

    def run(self):
        j = download_jobs[self.job_id]
        j["platform"] = detect_platform(self.url)
        out_dir = os.path.join(OUTPUT_BASE, j["platform"])
        os.makedirs(out_dir, exist_ok=True)

        log.info("JobLogger[%s]: starting download url=%s mode=%s", self.job_id, self.url, self.mode)
        log.info("JobLogger[%s]: out_dir=%s", self.job_id, out_dir)
        log.info("JobLogger[%s]: yt-dlp path=%s exists=%s", self.job_id, self.yt, os.path.isfile(self.yt))

        ffmpeg = _find_ffmpeg()
        ffmpeg_ok = ffmpeg is not None
        log.info("JobLogger[%s]: ffmpeg=%s", self.job_id, ffmpeg)

        if self.mode == "audio":
            fmt = "bestaudio[ext=m4a]/bestaudio"
            post = ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]
            if not ffmpeg_ok:
                j["log"].append("[warn] ffmpeg not found — audio extraction may fail")
        else:
            if ffmpeg_ok:
                # Don't restrict bestvideo to mp4 — for Shorts and some videos
                # the best video is webm/VP9/AV1. yt-dlp will merge + remux to mp4
                # via ffmpeg (--merge-output-format + --ffmpeg-location below).
                fmt = "bestvideo+bestaudio/best"
                post = ["--merge-output-format", "mp4"]
            else:
                # Without ffmpeg: try combined file first, then single-stream mp4
                fmt = "best[ext=mp4]/best"
                post = []
                j["log"].append("[warn] ffmpeg not found — downloading single-file format")

        out_tmpl = os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s")
        cmd = [self.yt, "-f", fmt, *post, "-o", out_tmpl,
               "--no-playlist", "--retries", "3",
               "--newline", "--progress", self.url]
        # Embedding metadata/thumbnails requires ffmpeg
        if ffmpeg_ok:
            cmd += ["--embed-metadata", "--embed-thumbnail"]

        if ffmpeg_ok:
            cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg)]

        j["log"].append(f"[yt-dlp] {self.yt}")
        j["log"].append(f"[cmd] {' '.join(cmd)}")
        log.info("JobLogger[%s]: cmd=%s", self.job_id, " ".join(cmd))

        try:
            log.info("JobLogger[%s]: calling _popen...", self.job_id)
            proc = _popen(cmd)
            _active_proc[0] = proc
            log.info("JobLogger[%s]: popen returned, pid=%s", self.job_id, proc.pid)
            # Wait for process to complete and read all output at once
            stdout_data, _ = proc.communicate(timeout=600)
            log.info("JobLogger[%s]: process exited, returncode=%d, output_chars=%d", self.job_id, proc.returncode, len(stdout_data))
            # Parse output line by line
            filepath = None
            for line in stdout_data.splitlines():
                j["log"].append(line)
                if "[download] Destination:" in line:
                    filepath = line.split("Destination:", 1)[1].strip()
                elif line.startswith("[Merger]") and "into" in line:
                    idx = line.rfind('"')
                    idx2 = line.rfind('"', 0, idx)
                    if idx > idx2:
                        filepath = line[idx2+1:idx]
            # Log last 5 lines for quick diagnosis
            last_lines = stdout_data.splitlines()[-5:] if stdout_data else []
            log.info("JobLogger[%s]: last output lines: %s", self.job_id, last_lines)

            if proc.returncode == 0:
                j["status"] = "done"
                if filepath and os.path.exists(filepath):
                    j["filepath"] = filepath
                    j["filename"] = os.path.basename(filepath)
                else:
                    files = sorted(
                        [f for f in os.listdir(out_dir) if not f.startswith(".")],
                        key=lambda f: os.path.getmtime(os.path.join(out_dir, f)),
                        reverse=True)
                    if files:
                        j["filepath"] = os.path.join(out_dir, files[0])
                        j["filename"] = files[0]
                size = os.path.getsize(j["filepath"]) if j.get("filepath") and os.path.exists(j.get("filepath", "")) else 0
                j["log"].append(f"[done] {j.get('filename','?')} ({_human(size)})")
                log.info("JobLogger[%s]: download complete: %s (%s)", self.job_id, j.get("filename", "?"), _human(size))
            else:
                j["status"] = "error"
                j["log"].append(f"[error] exit code {proc.returncode}")
                log.error("JobLogger[%s]: download failed (exit %d), output:\n%s", self.job_id, proc.returncode, stdout_data[-500:] if stdout_data else "(empty)")
        except FileNotFoundError as e:
            j["status"] = "error"
            j["log"].append(f"[error] yt-dlp not found: {self.yt}")
            j["log"].append(f"[error] {e}")
            log.error("JobLogger[%s]: yt-dlp not found: %s", self.job_id, self.yt)
        except Exception as e:
            j["status"] = "error"
            j["log"].append(f"[error] {e}")
            log.error("JobLogger[%s]: exception: %s", self.job_id, e, exc_info=True)
        finally:
            if _active_proc[0] is proc:
                _active_proc[0] = None

def _human(n):
    for u in ['B','KB','MB','GB']:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

# ── Main ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # If run directly (not via start.sh), do auto-setup
    auto_setup = "--auto-setup" in sys.argv or "--setup" in sys.argv

    if auto_setup:
        t = threading.Thread(target=run_setup, daemon=True)
        t.start()

    _safe_print(f"🎬 Video Downloader Server")
    _safe_print(f"   URL: http://localhost:{PORT}")
    _safe_print(f"   Output: {OUTPUT_BASE}/<platform>/")
    _safe_print()

    srv = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        _safe_print("\nDone.")
        srv.shutdown()
