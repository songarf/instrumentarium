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


# ── Embedded UI (auto-generated from download.html) ──────────────
_EMBEDDED_HTML = '<!DOCTYPE html>\n<html lang="ru">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>🎬 Video Downloader</title>\n<style>\n  * { box-sizing: border-box; margin: 0; padding: 0; }\n\n  body {\n    font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', sans-serif;\n    background: #0f0f1a;\n    color: #e0e0e0;\n    min-height: 100vh;\n    display: flex;\n    align-items: center;\n    justify-content: center;\n  }\n\n  .card {\n    background: #1a1a2e;\n    border: 1px solid #2a2a4a;\n    border-radius: 16px;\n    padding: 40px;\n    width: 540px;\n    max-width: 95vw;\n    box-shadow: 0 20px 60px rgba(0,0,0,.5);\n  }\n\n  h1 { font-size: 1.4rem; margin-bottom: 6px; color: #fff; }\n  .subtitle { font-size: .82rem; color: #666; margin-bottom: 28px; line-height: 1.5; }\n\n  /* ── Setup screen ──────────────────────────────────────── */\n  .setup-screen { text-align: center; }\n\n  .setup-icon {\n    font-size: 3.5rem; margin-bottom: 16px;\n    animation: pulse 2s ease-in-out infinite;\n  }\n  @keyframes pulse {\n    0%, 100% { transform: scale(1); }\n    50% { transform: scale(1.08); }\n  }\n\n  .setup-title { font-size: 1.15rem; color: #fff; margin-bottom: 8px; }\n  .setup-desc { font-size: .82rem; color: #888; margin-bottom: 28px; line-height: 1.6; }\n\n  .setup-btn {\n    display: inline-flex; align-items: center; gap: 10px;\n    padding: 14px 36px;\n    background: linear-gradient(135deg, #6c5ce7, #a78bfa);\n    border: none; border-radius: 12px; color: #fff;\n    font-size: 1.05rem; font-weight: 600; cursor: pointer;\n    transition: transform .15s, box-shadow .15s;\n  }\n  .setup-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(108,92,231,.45); }\n  .setup-btn:disabled { opacity: .5; cursor: wait; transform: none; box-shadow: none; }\n\n  /* ── Progress ───────────────────────────────────────────── */\n  .progress-section { margin-top: 24px; text-align: left; }\n\n  .progress-bg {\n    background: #12122a; border-radius: 8px; height: 8px; overflow: hidden;\n  }\n  .progress-bar {\n    height: 100%; width: 0%;\n    background: linear-gradient(90deg, #6c5ce7, #a78bfa, #6c5ce7);\n    background-size: 200% 100%;\n    border-radius: 8px;\n    transition: width .5s ease;\n    animation: shimmer 1.5s linear infinite;\n  }\n  @keyframes shimmer {\n    0% { background-position: 200% 0; }\n    100% { background-position: -200% 0; }\n  }\n\n  .progress-label {\n    display: flex; justify-content: space-between; align-items: center;\n    margin-top: 8px; font-size: .78rem;\n  }\n  .progress-pct { color: #a78bfa; font-weight: 600; }\n  .progress-status { color: #888; }\n\n  /* ── Download screen ────────────────────────────────────── */\n  .download-screen { display: none; }\n\n  label {\n    display: block; font-size: .78rem; text-transform: uppercase;\n    letter-spacing: .08em; color: #888; margin-bottom: 8px;\n  }\n\n  input[type="url"] {\n    width: 100%; background: #12122a; border: 1px solid #2a2a4a;\n    border-radius: 10px; padding: 12px 16px; color: #e0e0e0;\n    font-size: .95rem; outline: none; transition: border .2s; margin-bottom: 16px;\n  }\n  input[type="url"]:focus { border-color: #6c5ce7; }\n  input[type="url"]::placeholder { color: #444; }\n\n  .platform-badge {\n    display: inline-block; background: #12122a; border: 1px solid #2a2a4a;\n    border-radius: 6px; padding: 3px 10px; font-size: .75rem; color: #888;\n    margin-bottom: 18px; opacity: 0; transition: opacity .3s;\n  }\n  .platform-badge.visible { opacity: 1; }\n  .platform-youtube { color: #ff4757; border-color: #ff4757; }\n  .platform-twitter { color: #1da1f2; border-color: #1da1f2; }\n  .platform-tiktok { color: #ff0050; border-color: #ff0050; }\n  .platform-instagram { color: #e1306c; border-color: #e1306c; }\n  .platform-facebook { color: #1877f2; border-color: #1877f2; }\n  .platform-linkedin { color: #0077b5; border-color: #0077b5; }\n  .platform-other { color: #a78bfa; border-color: #a78bfa; }\n\n  .options { display: flex; gap: 12px; margin-bottom: 24px; }\n  .opt-btn {\n    flex: 1; background: #12122a; border: 1px solid #2a2a4a;\n    border-radius: 10px; padding: 14px 10px; text-align: center;\n    cursor: pointer; transition: all .2s; font-size: .85rem; color: #888;\n    user-select: none;\n  }\n  .opt-btn:hover { border-color: #4a4a6a; color: #ccc; }\n  .opt-btn.active { border-color: #6c5ce7; background: #1a1040; color: #a78bfa; }\n  .opt-btn .icon { font-size: 1.5rem; display: block; margin-bottom: 5px; }\n\n  .dl-btn {\n    width: 100%; padding: 14px;\n    background: linear-gradient(135deg, #6c5ce7, #a78bfa);\n    border: none; border-radius: 10px; color: #fff;\n    font-size: 1rem; font-weight: 600; cursor: pointer;\n    transition: transform .15s, box-shadow .15s;\n  }\n  .dl-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(108,92,231,.4); }\n  .dl-btn:disabled { opacity: .5; cursor: wait; transform: none; box-shadow: none; }\n\n  .dl-progress { margin-top: 18px; }\n  .dl-status { font-size: .82rem; color: #888; margin-top: 8px; }\n\n  /* ── Error notification ─────────────────────────────────── */\n  .error-toast {\n    display: none; margin-top: 12px; padding: 12px 16px;\n    background: #2a1010; border: 1px solid #ff4757; border-radius: 10px;\n    font-size: .82rem; color: #ff4757; line-height: 1.5;\n  }\n  .error-toast.visible { display: block; animation: fadeIn .3s ease; }\n  .error-toast .title { font-weight: 600; margin-bottom: 4px; }\n  .error-toast .hint { font-size: .72rem; color: #888; margin-top: 6px; }\n\n  .footer {\n    margin-top: 20px; font-size: .72rem; color: #444; text-align: center;\n  }\n\n  /* ── Transitions ────────────────────────────────────────── */\n  .fade-in { animation: fadeIn .4s ease; }\n  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }\n</style>\n</head>\n<body>\n<div class="card">\n\n  <!-- ═══════════════════════════════════════════════════════ -->\n  <!-- SETUP SCREEN                                           -->\n  <!-- ═══════════════════════════════════════════════════════ -->\n  <div class="setup-screen" id="setupScreen">\n    <div class="setup-icon">⚙️</div>\n    <div class="setup-title">Первоначальная настройка</div>\n    <div class="setup-desc">\n      Проверим и установим всё необходимое для скачивания видео.<br>\n      Python 3.7+, yt-dlp и папка для загрузок — всё автоматически.\n    </div>\n    <button class="setup-btn" id="setupBtn" onclick="startSetup()">\n      🚀 Настроить и запустить\n    </button>\n\n    <div class="progress-section" id="setupProgress" style="display:none">\n      <div class="progress-bg"><div class="progress-bar" id="setupBar"></div></div>\n      <div class="progress-label">\n        <span class="progress-status" id="setupStatus">Проверяю…</span>\n        <span class="progress-pct" id="setupPct">0%</span>\n      </div>\n    </div>\n  </div>\n\n  <!-- ═══════════════════════════════════════════════════════ -->\n  <!-- DOWNLOAD SCREEN                                        -->\n  <!-- ═══════════════════════════════════════════════════════ -->\n  <div class="download-screen" id="downloadScreen">\n    <h1>🎬 Video Downloader</h1>\n    <p class="subtitle">Скачай видео с YouTube, Twitter/X, TikTok, Instagram, Facebook, LinkedIn и 1000+ сайтов</p>\n\n    <label>Ссылка на видео</label>\n    <input type="url" id="url" placeholder="https://youtube.com/watch?v=…" autocomplete="off" autofocus>\n    <div class="platform-badge" id="badge">…</div>\n\n    <div class="options">\n      <div class="opt-btn active" id="optVideo" onclick="setMode(\'video\')">\n        <span class="icon">🎥</span>Видео (MP4)\n      </div>\n      <div class="opt-btn" id="optAudio" onclick="setMode(\'audio\')">\n        <span class="icon">🎵</span>Аудио (MP3)\n      </div>\n    </div>\n\n    <button class="dl-btn" id="dlBtn" onclick="download()">⬇️ Скачать</button>\n\n    <div class="dl-progress" id="dlProgress" style="display:none">\n      <div class="progress-bg"><div class="progress-bar" id="dlBar"></div></div>\n      <div class="dl-status" id="dlStatus"></div>\n      <div class="error-toast" id="errorToast">\n        <div class="title" id="errorTitle">❌ Ошибка</div>\n        <div class="message" id="errorMessage"></div>\n        <div class="hint">Подробности записаны в instrumentarium.log</div>\n      </div>\n    </div>\n\n    <p class="footer">Готово к работе ✅</p>\n  </div>\n\n</div>\n\n<script>\n/* ── Platform detect ─────────────────────────────────────── */\nconst PLATS = [\n  { name:\'youtube\',   hosts:[\'youtube.com\',\'youtu.be\'] },\n  { name:\'twitter\',   hosts:[\'twitter.com\',\'x.com\'] },\n  { name:\'tiktok\',    hosts:[\'tiktok.com\'] },\n  { name:\'instagram\', hosts:[\'instagram.com\'] },\n  { name:\'facebook\',  hosts:[\'facebook.com\',\'fb.com\',\'fb.watch\'] },\n  { name:\'linkedin\',  hosts:[\'linkedin.com\'] },\n];\nconst PLAT_CLS = { youtube:\'platform-youtube\', twitter:\'platform-twitter\', tiktok:\'platform-tiktok\',\n  instagram:\'platform-instagram\', facebook:\'platform-facebook\', linkedin:\'platform-linkedin\', other:\'platform-other\' };\nconst PLAT_LBL = { youtube:\'🔴 YouTube\', twitter:\'🐦 Twitter/X\', tiktok:\'🎵 TikTok\',\n  instagram:\'📸 Instagram\', facebook:\'📘 Facebook\', linkedin:\'💼 LinkedIn\', other:\'🌐 Другое\' };\n\nfunction detectPlatform(url) {\n  const u = url.toLowerCase();\n  for (const p of PLATS) for (const h of p.hosts) if (u.includes(h)) return p.name;\n  return \'other\';\n}\nfunction updateBadge(url) {\n  const b = document.getElementById(\'badge\');\n  if (!url) { b.classList.remove(\'visible\'); return; }\n  const p = detectPlatform(url);\n  b.textContent = \'Платформа: \' + (PLAT_LBL[p] || p);\n  b.className = \'platform-badge visible \' + (PLAT_CLS[p] || \'\');\n}\ndocument.getElementById(\'url\').addEventListener(\'input\', e => updateBadge(e.target.value));\ndocument.getElementById(\'url\').addEventListener(\'paste\', () =>\n  setTimeout(() => updateBadge(document.getElementById(\'url\').value), 50));\n\n/* ── Mode ─────────────────────────────────────────────────── */\nlet mode = \'video\';\nfunction setMode(m) {\n  mode = m;\n  document.getElementById(\'optVideo\').classList.toggle(\'active\', m === \'video\');\n  document.getElementById(\'optAudio\').classList.toggle(\'active\', m === \'audio\');\n}\n\n/* ── Bootstrap: check if setup already done ────────────────── */\nfetch(\'/status\').then(r => r.json()).then(d => {\n  if (d.phase === \'done\' && d.setup_done) {\n    // Already configured — skip setup, show download screen\n    document.getElementById(\'setupScreen\').style.display = \'none\';\n    document.getElementById(\'downloadScreen\').style.display = \'block\';\n    document.getElementById(\'downloadScreen\').classList.add(\'fade-in\');\n  }\n}).catch(() => {});\n\n/* ── Setup wizard ─────────────────────────────────────────── */\nlet setupPoll = null;\n\nfunction startSetup() {\n  const btn = document.getElementById(\'setupBtn\');\n  btn.disabled = true;\n  btn.textContent = \'⏳ Настраиваю…\';\n\n  document.getElementById(\'setupProgress\').style.display = \'block\';\n  document.getElementById(\'setupProgress\').classList.add(\'fade-in\');\n\n  // Start setup on server\n  fetch(\'/setup\', { method: \'POST\' }).then(r => r.json()).then(data => {\n    if (data.already_done) {\n      // Server says we\'re done — go straight to download\n      clearInterval(setupPoll);\n      document.getElementById(\'setupScreen\').style.display = \'none\';\n      document.getElementById(\'downloadScreen\').style.display = \'block\';\n      document.getElementById(\'downloadScreen\').classList.add(\'fade-in\');\n      return;\n    }\n    setupPoll = setInterval(pollSetup, 800);\n  }).catch(err => {\n    document.getElementById(\'setupStatus\').textContent = \'❌ Не удалось связаться с сервером\';\n    btn.disabled = false;\n    btn.textContent = \'🔄 Попробовать снова\';\n  });\n}\n\nfunction pollSetup() {\n  fetch(\'/status\').then(r => r.json()).then(d => {\n    document.getElementById(\'setupBar\').style.width = (d.progress || 0) + \'%\';\n    document.getElementById(\'setupPct\').textContent = (d.progress || 0) + \'%\';\n\n    // Phase labels\n    const PHASE_LABELS = {\n      idle: \'⏳ Ожидание…\',\n      checking: \'🔍 Проверяю зависимости…\',\n      silent_check: \'🔍 Тихая проверка…\',\n      installing_python: \'🐍 Устанавливаю Python…\',\n      installing_ytdlp: \'📦 Скачиваю yt-dlp…\',\n      done: \'✅ Всё готово!\',\n      error: \'❌ Ошибка\',\n    };\n    document.getElementById(\'setupStatus\').textContent = PHASE_LABELS[d.phase] || d.phase;\n\n    // Update status text from messages (last message only)\n    if (d.messages && d.messages.length > 0) {\n      const last = d.messages[d.messages.length - 1];\n      if (last.text && !last.text.startsWith(\'✅\') && !last.text.startsWith(\'❌\')) {\n        document.getElementById(\'setupStatus\').textContent = last.text;\n      }\n    }\n\n    if (d.phase === \'done\') {\n      clearInterval(setupPoll);\n      document.getElementById(\'setupStatus\').textContent = \'✅ Всё готово! Открываю…\';\n      setTimeout(() => {\n        document.getElementById(\'setupScreen\').style.display = \'none\';\n        document.getElementById(\'downloadScreen\').style.display = \'block\';\n        document.getElementById(\'downloadScreen\').classList.add(\'fade-in\');\n      }, 1200);\n    }\n\n    if (d.phase === \'error\') {\n      clearInterval(setupPoll);\n      const btn = document.getElementById(\'setupBtn\');\n      btn.disabled = false;\n      btn.textContent = \'🔄 Попробовать снова\';\n    }\n  }).catch(() => {});\n}\n\n/* ── Download ─────────────────────────────────────────────── */\nlet dlPoll = null;\n\nfunction showError(title, message) {\n  document.getElementById(\'errorTitle\').textContent = title;\n  document.getElementById(\'errorMessage\').textContent = message;\n  document.getElementById(\'errorToast\').classList.add(\'visible\');\n}\n\nfunction hideError() {\n  document.getElementById(\'errorToast\').classList.remove(\'visible\');\n}\n\nfunction download() {\n  const url = document.getElementById(\'url\').value.trim();\n  if (!url) { showError(\'Введи ссылку\', \'Пожалуйста, вставь ссылку на видео\'); return; }\n\n  document.getElementById(\'dlProgress\').style.display = \'block\';\n  document.getElementById(\'dlProgress\').classList.add(\'fade-in\');\n  hideError();\n  document.getElementById(\'dlBar\').style.width = \'5%\';\n  document.getElementById(\'dlStatus\').textContent = \'Запуск…\';\n\n  const btn = document.getElementById(\'dlBtn\');\n  btn.disabled = true; btn.textContent = \'⏳ Скачивание…\';\n\n  fetch(\'/download\', {\n    method: \'POST\',\n    headers: { \'Content-Type\': \'application/json\' },\n    body: JSON.stringify({ url, mode })\n  })\n  .then(r => r.json())\n  .then(data => {\n    if (data.error) {\n      showError(\'Ошибка\', data.error);\n      btn.disabled = false; btn.textContent = \'⬇️ Скачать\';\n      return;\n    }\n    document.getElementById(\'dlStatus\').textContent = `📦 ${data.platform} — скачивание…`;\n    let offset = 0;\n    dlPoll = setInterval(() => {\n      fetch(\'/log?job=\' + data.job_id + \'&offset=\' + offset)\n        .then(r => r.json())\n        .then(d => {\n          if (d.lines) {\n            // Show last line as status\n            const last = d.lines[d.lines.length - 1];\n            if (last && !last.startsWith(\'[yt-dlp]\') && !last.startsWith(\'[cmd]\')) {\n              document.getElementById(\'dlStatus\').textContent = last;\n            }\n            // If there\'s an error in logs, show toast\n            d.lines.forEach(l => {\n              if (l.includes(\'[error]\') || l.includes(\'ERROR\') || l.includes(\'Error\')) {\n                showError(\'Ошибка загрузки\', l);\n              }\n            });\n            offset += d.lines.length;\n          }\n          if (d.status === \'done\' || d.status === \'error\') {\n            clearInterval(dlPoll);\n            document.getElementById(\'dlBar\').style.width = \'100%\';\n            if (d.status === \'done\') {\n              document.getElementById(\'dlStatus\').textContent = \'✅ Готово!\';\n            }\n            btn.disabled = false; btn.textContent = \'⬇️ Скачать\';\n          } else {\n            const bar = document.getElementById(\'dlBar\');\n            const cur = parseFloat(bar.style.width);\n            if (cur < 92) bar.style.width = (cur + Math.random() * 6) + \'%\';\n          }\n        }).catch(() => {});\n    }, 1500);\n  })\n  .catch(err => {\n    showError(\'Ошибка соединения\', err.message);\n    btn.disabled = false; btn.textContent = \'⬇️ Скачать\';\n  });\n}\n\n</script>\n</body>\n</html>\n'

# ── Config ──────────────────────────────────────────────────────────
PORT = 18765

# ── Persistent state directory ──────────────────────────────────────
# Use %LOCALAPPDATA%\Instrumentarium for all persistent files so they
# survive antivirus cleanup, OneDrive sync issues, etc.
if platform.system() == "Windows":
    _PERSIST_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Instrumentarium")
else:
    _PERSIST_DIR = os.path.join(os.environ.get("HOME", ""), ".instrumentarium")
os.makedirs(_PERSIST_DIR, exist_ok=True)

SETUP_MARKER = os.path.join(_PERSIST_DIR, ".setup_done")
_LOCK_PATH = os.path.join(_PERSIST_DIR, ".instrumentarium.lock")

# When running from PyInstaller, __file__ points to temp _MEI dir.
# Use sys.executable location for runtime data (downloads, .bin).
if hasattr(sys, "_MEIPASS"):
    _EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    SCRIPT_DIR = _EXE_DIR
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_BASE = os.path.join(SCRIPT_DIR, "downloads")

# yt-dlp binary locations
if hasattr(sys, "_MEIPASS"):
    _BIN_CANDIDATES = [
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
    """Check if yt-dlp exists in any known location."""
    # Check all bin candidates (beside exe first, then bundle)
    for d in _BIN_CANDIDATES:
        candidate = os.path.join(d, "yt-dlp.exe" if platform.system() == "Windows" else "yt-dlp")
        if os.path.isfile(candidate):
            try:
                out = subprocess.check_output([candidate, "--version"], stderr=subprocess.STDOUT, text=True,
                                             creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0).strip()
                return True, out
            except:
                pass
    # Also check system PATH
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
        log.warning("Could not write setup marker to %s: %s", SETUP_MARKER, e)

def _clear_marker():
    """Remove .setup_done marker file."""
    try:
        if os.path.exists(SETUP_MARKER):
            log.info("Removing setup marker: %s", SETUP_MARKER)
            os.remove(SETUP_MARKER)
    except Exception as e:
        log.warning("Could not remove setup marker: %s", e)

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
            # Find yt-dlp: check all candidates, then system PATH
            yt = None
            for d in _BIN_CANDIDATES:
                candidate = os.path.join(d, "yt-dlp.exe" if platform.system() == "Windows" else "yt-dlp")
                if os.path.isfile(candidate):
                    yt = candidate
                    break
            if not yt:
                yt = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe") or "yt-dlp"
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
        """Serve the embedded HTML UI from memory."""
        body = _EMBEDDED_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

        # Check if ffmpeg is available — adapt format/merge strategy
        ffmpeg = _find_ffmpeg()
        ffmpeg_ok = ffmpeg is not None

        if self.mode == "audio":
            fmt = "bestaudio[ext=m4a]/bestaudio"
            post = ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]
            # ffmpeg needed for audio extraction too
            if not ffmpeg_ok:
                j["log"].append("[warn] ffmpeg not found — audio extraction may fail. Install ffmpeg for best results.")
        else:
            if ffmpeg_ok:
                # ffmpeg available: download best video+audio and merge
                fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                post = ["--merge-output-format", "mp4"]
            else:
                # No ffmpeg: download single-file format (video+audio muxed)
                fmt = "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
                post = []  # no merge without ffmpeg
                j["log"].append("[warn] ffmpeg not found — downloading single-file format (may be lower quality)")

        out_tmpl = os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s")
        cmd = [self.yt, "-f", fmt, *post, "-o", out_tmpl,
               "--no-playlist", "--retries", "3",
               "--embed-metadata", "--embed-thumbnail",
               "--newline", "--progress", self.url]

        if ffmpeg_ok:
            cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg)]

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
                log.info("Download complete: %s (%s)", j.get("filename","?"), _human(size))
            else:
                j["status"] = "error"
                j["log"].append(f"[error] exit code {proc.returncode}")
                log.error("Download failed (exit %d): url=%s", proc.returncode, self.url)
                # Collect stderr if any
                try:
                    remaining = proc.stdout.read() if proc.stdout else ""
                    if remaining:
                        j["log"].append(f"[stderr] {remaining.strip()}")
                        log.error("yt-dlp stderr: %s", remaining.strip())
                except Exception:
                    pass
        except FileNotFoundError as e:
            j["status"] = "error"
            j["log"].append(f"[error] yt-dlp not found: {self.yt}")
            j["log"].append(f"[error] {e}")
            log.error("yt-dlp not found: %s (url=%s)", self.yt, self.url)
        except Exception as e:
            j["status"] = "error"
            j["log"].append(f"[error] {e}")
            log.error("Download error: %s (url=%s)", e, self.url, exc_info=True)

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
