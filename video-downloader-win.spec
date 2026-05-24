# Video Downloader — PyInstaller spec for Windows
# Build on Windows: pyinstaller video-downloader-win.spec

block_cipher = None

# Collect all pywebview submodules (needed for edgechromium on Windows)
try:
    from PyInstaller.utils.hooks import collect_all
    webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')
except Exception:
    webview_datas, webview_binaries, webview_hiddenimports = [], [], ['webview']

# Collect CEF Python dependencies (Chromium Embedded Framework for Windows)
cef_binaries, cef_datas, cef_imports = [], [], []
try:
    from PyInstaller.utils.hooks import collect_all
    cef_binaries, cef_datas, cef_imports = collect_all('cefpython3')
except Exception:
    cef_imports = ['cefpython3']

a = Analysis(
    ['app.py', 'server.py'],
    pathex=[],
    binaries=webview_binaries + cef_binaries,
    datas=webview_datas + cef_datas + [
        ('download.html', '.'),
    ],
    hiddenimports=webview_hiddenimports + cef_imports + [
        'bottle', 'proxy_tools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Instrumentarium',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)