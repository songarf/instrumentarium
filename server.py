#!/usr/bin/env python3
"""
Instrumentarium — Setup Wizard + Server
Checks dependencies, installs yt-dlp, starts the server, opens browser.
"""

import http.server, json, logging, os, platform, shutil, ssl, subprocess, sys, threading, time, urllib.request, uuid, zipfile
from urllib.parse import urlparse, parse_qs

# ── Logging ──────────────────────────────────────────────────────────
log = logging.getLogger("instrumentarium.server")

def _safe_print(*args, **kwargs):
    """Print safely — skip when stdout is None (PyInstaller console=False on Windows)."""
    if sys.stdout:
        try:
            print(*args, **kwargs)
        except Exception:
            pass

# ── Config ──────────────────────────────────────────────────────────
PORT = 18765
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_BASE = os.path.join(SCRIPT_DIR, "downloads")
YT_DLP_DIR = os.path.join(SCRIPT_DIR, ".bin")
YT_DLP = os.path.join(YT_DLP_DIR, "yt-dlp.exe" if platform.system() == "Windows" else "yt-dlp")
SETUP_MARKER = os.path.join(SCRIPT_DIR, ".setup_done")

# ── Subprocess helper — no console windows on Windows ───────────────
def _popen(cmd, **kwargs):
    """subprocess.Popen that never flashes a console window on Windows."""
    if platform.system() == "Windows":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.STDOUT)
    kwargs.setdefault("text", True)
    kwargs.setdefault("bufsize", 1)
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
    """Check if yt-dlp exists in .bin/ or system PATH."""
    if os.path.isfile(YT_DLP):
        try:
            out = subprocess.check_output([YT_DLP, "--version"], stderr=subprocess.STDOUT, text=True,
                                         creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0).strip()
            return True, out
        except:
            pass
    sys_yt = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if sys_yt:
        try:
            out = subprocess.check_output([sys_yt, "--version"], stderr=subprocess.STDOUT, text=True,
                                         creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0).strip()
            return True, out
        except:
            pass
    return False, None

def install_ytdlp():
    """Download yt-dlp into .bin/."""
    os.makedirs(YT_DLP_DIR, exist_ok=True)
    is_win = platform.system() == "Windows"
    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" if is_win \
          else "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"

    setup_state["phase"] = "installing_ytdlp"
    msg(f"⬇️  Скачиваю yt-dlp…", "info")
    log.info("Downloading yt-dlp from %s", url)
    setup_state["progress"] = 50

    try:
        urllib.request.urlretrieve(url, YT_DLP)
        if not is_win:
            os.chmod(YT_DLP, 0o755)
        ver = subprocess.check_output([YT_DLP, "--version"], stderr=subprocess.STDOUT, text=True).strip()
        msg(f"✅ yt-dlp {ver} установлен", "ok")
        log.info("yt-dlp %s installed at %s", ver, YT_DLP)
        setup_state["progress"] = 70
        return True
    except Exception as e:
        msg(f"❌ Ошибка загрузки yt-dlp: {e}", "err")
        log.error("yt-dlp installation failed: %s", e)
        setup_state["error"] = str(e)
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

# ── Full setup runner ────────────────────────────────────────────────
def _write_marker():
    """Write .setup_done marker file."""
    try:
        with open(SETUP_MARKER, "w") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        log.warning("Could not write setup marker: %s", e)

def _clear_marker():
    """Remove .setup_done marker file."""
    try:
        if os.path.exists(SETUP_MARKER):
            os.remove(SETUP_MARKER)
    except Exception:
        pass

def _ensure_deps():
    """Silent dependency check — no messages, no UI.
    Returns True if all deps OK, False if setup is needed.
    """
    # Python
    py_path, _ = find_system_python()
    if not py_path:
        log.warning("Silent check: Python not found, setup needed")
        return False

    # yt-dlp
    ok, _ = check_ytdlp()
    if not ok:
        log.info("Silent check: yt-dlp not found, will download")
        if not install_ytdlp():
            return False

    os.makedirs(OUTPUT_BASE, exist_ok=True)
    setup_state["python_ok"] = True
    setup_state["ytdlp_ok"] = True
    setup_state["phase"] = "done"
    setup_state["progress"] = 100
    setup_state["server_started"] = True
    _write_marker()
    log.info("Silent check passed — all deps OK")
    return True

def run_setup():
    """Full visible setup: check Python → check/install ytdlp → start server."""
    setup_state["phase"] = "checking"
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
            self._serve_html()
            return

        if p.path == "/status":
            # On first contact, check if setup was already done
            if setup_state["phase"] == "idle" and os.path.exists(SETUP_MARKER):
                if _ensure_deps():
                    setup_state["setup_done"] = True
                else:
                    # Marker exists but deps are gone — reset
                    setup_state["phase"] = "idle"
                    setup_state["setup_done"] = False
            self._json({
                "phase": setup_state["phase"],
                "progress": setup_state["progress"],
                "messages": setup_state["messages"],
                "python_ok": setup_state["python_ok"],
                "ytdlp_ok": setup_state["ytdlp_ok"],
                "server_started": setup_state["server_started"],
                "error": setup_state["error"],
                "setup_done": os.path.exists(SETUP_MARKER),
            })
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
            if setup_state["phase"] != "done":
                self._json({"error": "Setup not complete"})
                return
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            url = body.get("url", "").strip()
            mode = body.get("mode", "video")
            if not url:
                self._json({"error": "URL is required"})
                return
            jid = str(uuid.uuid4())[:8]
            download_jobs[jid] = {"log": [], "status": "running"}
            yt = YT_DLP if os.path.isfile(YT_DLP) else shutil.which("yt-dlp") or "yt-dlp"
            JobLogger(jid, url, mode, yt).start()
            self._json({"job_id": jid, "platform": detect_platform(url)})
            return

        self.send_error(404)

    def log_message(self, *a): pass

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self):
        html_path = os.path.join(SCRIPT_DIR, "download.html")
        try:
            with open(html_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404, "download.html not found")

# ── Download job logger ─────────────────────────────────────────────
download_jobs = {}

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

        if self.mode == "audio":
            fmt = "bestaudio[ext=m4a]/bestaudio"
            post = ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]
        else:
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            post = ["--merge-output-format", "mp4"]

        out_tmpl = os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s")
        cmd = [self.yt, "-f", fmt, *post, "-o", out_tmpl,
               "--no-playlist", "--retries", "3",
               "--embed-metadata", "--embed-thumbnail",
               "--newline", "--progress", self.url]

        j["log"].append(f"[yt-dlp] {self.yt}")
        j["log"].append(f"[cmd] {' '.join(cmd)}")

        try:
            proc = _popen(cmd)
            filepath = None
            for line in proc.stdout:
                line = line.rstrip()
                if not line: continue
                j["log"].append(line)
                if "[download] Destination:" in line:
                    filepath = line.split("Destination:", 1)[1].strip()
                elif line.startswith("[Merger]") and "into" in line:
                    idx = line.rfind('"'); idx2 = line.rfind('"', 0, idx)
                    if idx > idx2: filepath = line[idx2+1:idx]
            proc.wait()

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
                size = os.path.getsize(j["filepath"]) if j.get("filepath") and os.path.exists(j.get("filepath","")) else 0
                j["log"].append(f"[done] {j.get('filename','?')} ({_human(size)})")
            else:
                j["status"] = "error"
                j["log"].append(f"[error] exit code {proc.returncode}")
                # Collect stderr if any
                try:
                    remaining = proc.stdout.read() if proc.stdout else ""
                    if remaining:
                        j["log"].append(f"[stderr] {remaining.strip()}")
                except Exception:
                    pass
        except FileNotFoundError as e:
            j["status"] = "error"
            j["log"].append(f"[error] yt-dlp not found: {self.yt}")
            j["log"].append(f"[error] {e}")
        except Exception as e:
            j["status"] = "error"
            j["log"].append(f"[error] {e}")

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
