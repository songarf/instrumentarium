# 🎬 Instrumentarium — Build Instructions

## Project Structure

```
Instrumentarium/
├── app.py                      # Desktop launcher (pywebview → native window 620×700)
├── server.py                   # Backend: setup wizard + HTTP server (port 18765) + yt-dlp
├── download.html               # UI: setup wizard + downloader (dark theme)
├── start.sh / start.bat        # Quick launch scripts (no build needed)
├── assets/
│   ├── icon.svg                # Source icon
│   ├── icon.png                # Generated icon (512×512, in git)
│   ├── icon.ico                # Generated icon (256×256, in git)
│   └── icon_build.py           # SVG → .ico/.png converter (utility, not needed in CI)
├── tests/
│   └── test_server.py          # 22 tests (pytest)
├── video-downloader.spec       # PyInstaller spec (Linux/macOS)
├── video-downloader-win.spec   # PyInstaller spec (Windows)
├── pytest.ini                  # Pytest config
├── .github/workflows/build.yml # CI/CD
└── downloads/                  # Output folder (organized by platform)
```

## Prerequisites (all platforms)

- Python 3.7+
- pip

## Quick Launch (no build)

### Linux / macOS / WSL
```bash
bash start.sh
```

### Windows
```
start.bat
```

---

## Building Portable Binaries

### 🐧 Linux Binary

```bash
pip install pyinstaller pywebview
pyinstaller video-downloader.spec
# Output: dist/VideoDownloader (standalone binary)
```

### 🪟 Windows .exe

```powershell
pip install pyinstaller pywebview
pyinstaller video-downloader-win.spec
# Output: dist/VideoDownloader.exe
```

### 🍎 macOS Binary

```bash
pip3 install pyinstaller pywebview
pyinstaller video-downloader.spec
# Output: dist/VideoDownloader
```

---

## GitHub Actions (Automated Cross-Platform Builds)

CI runs automatically on push to `main` or tag `v*`.

**Pipeline:**
1. **test** (ubuntu) — `python -m pytest tests/ -v`
2. **build** (matrix: linux/windows/macos, fail-fast: false) — PyInstaller → portable archive
3. **release** (tag v* only) — GitHub Release with all archives

**Artifacts (portable, no installers):**
- `VideoDownloader-linux.tar.gz`
- `VideoDownloader-windows.zip`
- `VideoDownloader-macos.tar.gz`

Icons are pre-generated in git (`assets/icon.png`, `assets/icon.ico`) — no build step needed in CI.
