#!/usr/bin/env python3
"""
Video Downloader — Desktop App Launcher
Opens a native window with the HTML UI and runs the backend server.
"""

import os, sys, threading, webview

# ── Paths ──────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(SCRIPT_DIR, "server.py")

# ── Start the backend server in a background thread ────────────────
def start_server():
    import subprocess
    # Run server.py on port 18765
    subprocess.Popen(
        [sys.executable, SERVER_PY, "--auto-setup"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=SCRIPT_DIR,
    )

threading.Thread(target=start_server, daemon=True).start()

# ── Open native window ─────────────────────────────────────────────
webview.create_window(
    "🎬 Video Downloader",
    "http://localhost:18765",
    width=620,
    height=700,
    resizable=True,
    min_size=(480, 560),
)

webview.start()
