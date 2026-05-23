# 🎬 Video Downloader — Build Instructions

## Project Structure

```
video-downloader/
├── app.py                      # Desktop launcher (pywebview)
├── server.py                   # Backend server (setup + yt-dlp)
├── download.html               # UI (setup wizard + downloader)
├── start.sh / start.bat        # Quick launch scripts (no build needed)
├── video-downloader.spec       # PyInstaller spec (Linux/macOS)
├── video-downloader-win.spec   # PyInstaller spec (Windows)
└── dist/                       # Build output
```

## Prerequisites (all platforms)

- Python 3.7+
- pip

## Quick Launch (no build)

### Linux / macOS / WSL
```bash
./start.sh
```

### Windows
```
start.bat
```

---

## Building Installers

### 🐧 Linux AppImage / Binary

```bash
pip install pyinstaller pywebview
pyinstaller video-downloader.spec
# Output: dist/linux/VideoDownloader (20 MB standalone binary)
```

To create a `.deb` package:
```bash
# Install dpkg
sudo apt install dpkg-dev

# Create package structure
mkdir -p video-downloader-pkg/usr/bin
cp dist/linux/VideoDownloader video-downloader-pkg/usr/bin/video-downloader

# Build .deb
dpkg-deb --build video-downloader-pkg
# Output: video-downloader-pkg.deb
```

### 🪟 Windows .exe + Installer

**On a Windows machine:**

```powershell
# 1. Install Python 3.7+ from python.org (check "Add to PATH")

# 2. Install dependencies
pip install pyinstaller pywebview

# 3. Build
pyinstaller video-downloader-win.spec
# Output: dist\windows\VideoDownloader.exe
```

**To create an installer with desktop shortcut:**

Option A — Inno Setup (recommended):
```powershell
# Download Inno Setup from https://jrsoftware.org/isinfo.php
# Create a script (installer.iss) — see below
# Compile with ISCC installer.iss
```

`installer.iss` template:
```iss
[Setup]
AppName=Video Downloader
AppVersion=1.0
DefaultDirName={autopf}\VideoDownloader
DefaultGroupName=Video Downloader
OutputBaseFilename=VideoDownloader-Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\windows\VideoDownloader.exe"; DestDir: "{app}"; DestName: "VideoDownloader.exe"

[Icons]
Name: "{autodesktop}\Video Downloader"; Filename: "{app}\VideoDownloader.exe"
Name: "{group}\Video Downloader"; Filename: "{app}\VideoDownloader.exe"
Name: "{group}\Uninstall Video Downloader"; Filename: "{uninstallexe}"
```

Option B — NSIS:
```powershell
# Install NSIS from https://nsis.sourceforge.io
makensis installer.nsi
```

### 🍎 macOS .app + .dmg

**On a macOS machine:**

```bash
# 1. Install Python 3.7+
brew install python3

# 2. Install dependencies
pip3 install pyinstaller pywebview

# 3. Build .app bundle
pyinstaller video-downloader.spec --osx-bundle-identifier com.soncra.videodownloader
# Output: dist/macos/VideoDownloader.app
```

**To create a .dmg:**

```bash
# Install create-dmg
brew install create-dmg

create-dmg \
  --volname "Video Downloader" \
  --volicon "icon.icns" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --app-drop-link 425 178 \
  "VideoDownloader.dmg" \
  "dist/macos/VideoDownloader.app"
```

---

## GitHub Actions (Automated Cross-Platform Builds)

Create `.github/workflows/build.yml`:

```yaml
name: Build Installers

on:
  push:
    tags: ['v*']

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - run: pip install pyinstaller pywebview

      - name: Build (Linux)
        if: runner.os == 'Linux'
        run: pyinstaller video-downloader.spec

      - name: Build (Windows)
        if: runner.os == 'Windows'
        run: pyinstaller video-downloader-win.spec

      - name: Build (macOS)
        if: runner.os == 'macOS'
        run: pyinstaller video-downloader.spec --osx-bundle-identifier com.soncra.videodownloader

      - uses: actions/upload-artifact@v4
        with:
          name: ${{ runner.os }}-build
          path: dist/
```

This produces:
- `dist/linux/VideoDownloader` — Linux binary
- `dist/windows/VideoDownloader.exe` — Windows executable  
- `dist/macos/VideoDownloader.app` — macOS app bundle
