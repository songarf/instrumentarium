# INSTRUMENTARIUM — Build & Architecture Reference

*Этот документ — полное описание архитектуры, файлов, потоков данных и поведения приложения. Читать при начале любой новой сессии работы.*

---

## Содержание

1. [Что это за приложение](#1-что-это-за-приложение)
2. [Структура файлов](#2-структура-файлов)
3. [Архитектура: как всё работает](#3-архитектура-как-всё-работает)
4. [Потоки (Threads)](#4-потоки-threads)
5. [HTTP API](#5-http-api)
6. [Рабочие файлы](#6-рабочие-файлы)
7. [Форматы видео/аудио](#7-форматы-видеоаудио)
8. [Сборка (PyInstaller)](#8-сборка-pyinstaller)
9. [CI/CD](#9-cicd)
10. [Тестирование](#10-тестирование)
11. [Известные ограничения и планы](#11-известные-ограничения-и-планы)

---

## 1. Что это за приложение

**Instrumentarium** — портативное десктопное приложение для скачивания видео с YouTube, Twitter/X, TikTok, Instagram, Facebook, LinkedIn и 1000+ других сайтов.

**Ключевой принцип:** Распаковал → запустил → вставил ссылку → скачал. Без установщиков, без командной строки, без настройки. Всё в одной папке.

**Целевые платформы:** Windows, Linux, macOS

**Технологический стек:**
- Python 3.7+ (встроенный в билд)
- yt-dlp (скачивается автоматически при первом запуске)
- ffmpeg (скачивается автоматически на Windows)
- pywebview (нативное окно с HTML/CSS/JS UI)
- cefpython3 (Chromium Embedded Framework — fallback для Windows без WebView2)
- PyInstaller (сборка в standalone-бинарь)

---

## 2. Структура файлов

```
instrumentarium/
├── app.py                      # Точка входа: лаунчер, сервер, окно
├── server.py                   # Backend: setup wizard, HTTP API, yt-dlp
├── download.html               # UI: setup wizard + загрузчик (тёмная тема, русский)
├── start.sh                    # Быстрый запуск (Linux/macOS/WSL)
├── start.bat                   # Быстрый запуск (Windows)
├── assets/
│   ├── icon.svg                # Исходная иконка (вектор)
│   ├── icon.png                # Иконка 512×512 (сгенерирована из SVG, в git)
│   ├── icon.ico                # Иконка 256×256 для Windows (сгенерирована, в git)
│   └── icon_build.py           # Утилита SVG → .ico/.png (не нужна в CI)
├── tests/
│   └── test_server.py          # 22 теста (pytest)
├── video-downloader.spec       # PyInstaller spec (Linux/macOS)
├── video-downloader-win.spec   # PyInstaller spec (Windows)
├── pytest.ini                  # Конфиг pytest
├── .github/workflows/build.yml # CI/CD
├── .gitignore                  # CONTEXT.md игнорируется
├── BUILD.md                    # Этот файл
├── SPEC.md                     # Техническая спецификация
├── USER_GUIDE.md               # Руководство пользователя
├── README.md                   # Описание проекта для GitHub
└── downloads/                  # ← Создаётся автоматически (папка платформ)
```

### Файлы, генерируемые при работе (все в папке с .exe):

```
<папка с .exe>/
├── instrumentarium.log         # Лог приложения (debug level)
├── .setup_done                 # Маркёр завершённой настройки (timestamp)
├── .instrumentarium.lock       # Lock-файл для единственного инстанса
├── .cookies.txt                # Cookies файл (LinkedIn и др., в .gitignore)
├── .bin/                       # Скачанные бинарники
│   ├── yt-dlp.exe              # (Windows) или yt-dlp (Linux/macOS)
│   ├── ffmpeg.exe              # (Windows, скачивается автоматически)
│   └── ffprobe.exe             # (Windows, скачивается автоматически)
└── downloads/                  # Скачанные видео
    ├── youtube/
    ├── twitter/
    ├── tiktok/
    ├── instagram/
    ├── facebook/
    ├── linkedin/
    └── other/
```

**Важно:** Все рабочие файлы — в одной папке с исполняемым файлом. Ничего не пишется в AppData, ~/.instrumentarium, или куда-либо ещё.

---

## 3. Архитектура: как всё работает

### 3.1. Точка входа: app.py

```
app.py (main thread)
  │
  ├── 1. Настройка stdout/stderr → devnull (Windows, console=False)
  │
  ├── 2. Вычисление _BASE_DIR:
  │       PyInstaller: dirname(sys.executable) — папка с .exe
  │       Dev:         dirname(__file__) — папка со скриптом
  │
  ├── 3. Настройка logging → FileHandler(_BASE_DIR/instrumentarium.log)
  │
  ├── 4. Single-instance lock:
  │       _BASE_DIR/.instrumentarium.lock
  │       Windows: msvcrt.locking()
  │       Unix:    fcntl.flock()
  │       Если lock не взят → выход (уже запущен)
  │
  ├── 5. Запуск server_thread (daemon):
  │       ├── import server
  │       ├── os.chdir(_BASE_DIR)
  │       ├── Проверка .setup_done:
  │       │   Есть → phase="silent_check", _ensure_deps() в фоне
  │       │   Нет  → run_setup() в фоне (показать wizard)
  │       └── HTTP server на 0.0.0.0:18765 (timeout=0.5s)
  │
  ├── 6. Ожидание готовности сервера (max 5s, polling 127.0.0.1:18765)
  │
  └── 7. Открытие окна pywebview:
          Размер: 620×720, resizable=False
          Windows: edgechromium → auto-detect (CEF удалён для уменьшения размера билда)
          Linux:   auto-detect (GTK/Qt)
          macOS:   auto-detect (Cocoa)
          При закрытии → HTTP POST /shutdown → kill subprocess → stop server (без sleep, мгновенный exit)
```

### 3.2. Backend: server.py

```
server.py (импортируется как модуль из app.py)
  │
  ├── Конфигурация:
  │     PORT = 18765
  │     _BASE_DIR = вычисляется так же как в app.py
  │     SETUP_MARKER = _BASE_DIR/.setup_done
  │     OUTPUT_BASE  = _BASE_DIR/downloads
  │     _BIN_CANDIDATES = [_BASE_DIR/.bin, _EXE_DIR/.bin, _MEIPASS/.bin]
  │     YT_DLP = _BIN_CANDIDATES[0]/yt-dlp.exe
  │
  ├── setup_state (глобальный dict, shared между потоками):
  │     phase: idle | checking | silent_check | installing_python |
  │             installing_ytdlp | installing_ffmpeg | done | error
  │     progress: 0-100
  │     messages: [{text, type, time}]
  │     python_ok, ytdlp_ok, server_started, error
  │
  ├── _active_proc = [None] — текущий запущенный yt-dlp subprocess
  │     (list-based mutable global, для kill при shutdown)
  │
  ├── HTTP Handler:
  │     GET  /              → download.html
  │     GET  /status        → JSON setup_state
  │     GET  /probe?url=    → JSON {title, formats, audio_formats}
  │     GET  /log?job=&offset= → JSON {lines, status}
  │     GET  /open-folder   → открыть папку downloads в файловом менеджере
  │     POST /setup         → запустить setup wizard
  │     POST /download      → запустить скачивание
  │     POST /shutdown      → kill subprocess + stop server
  │
  ├── Setup flow:
  │     run_setup() — полный wizard (первый запуск):
  │       1. find_system_python()
  │       2. check_ytdlp() / install_ytdlp()
  │       3. install_ffmpeg() (best-effort)
  │       4. _write_marker()
  │
  │     _ensure_deps() — тихая проверка (повторный запуск):
  │       1. find_system_python()
  │       2. check_ytdlp() / install_ytdlp()
  │       3. install_ffmpeg() (best-effort)
  │       4. _write_marker()
  │
  ├── Probe flow (/probe):
  │     yt-dlp --dump-single-json → parse formats:
  │       - is_video: (vcodec != "none" and vcodec is not None) or
  │                   (video_ext != "none" and video_ext is not None)
  │       - eff_height: width for vertical, height for horizontal
  │       - display_label: format_note → eff_height → format_id → "Скачать видео"
  │       - Дедупликация по стандартным бакетам
  │       - audio_formats: дедупликация по битрейту
  │
  └── Download flow (JobLogger):
        - Video: format_id+bestaudio/best → --merge-output-format mp4
        - Audio: bestaudio[ext=m4a]/bestaudio → --extract-audio → mp3
        - Если ffmpeg: --recode-video mp4, --embed-metadata, --embed-thumbnail
        - Имя файла: %(title).120s [%(id)s].%(ext)s (ограничение 120 символов)
```

---

## 4. Потоки (Threads)

```
Main Thread (app.py)
  └── pywebview event loop (блокирует main thread)

Server Thread (daemon, app.py → _start_server_in_thread)
  └── http.server.HTTPServer.serve_forever(timeout=0.5)
        └── Handler.do_GET/do_POST (вызывается из HTTP-потока сервера)

Setup Thread (daemon, server.py → run_setup или _ensure_deps)
  └── Проверка/установка Python, yt-dlp, ffmpeg

Download Thread (daemon, server.py → JobLogger)
  └── subprocess.Popen(yt-dlp) → proc.communicate() → parse stdout
```

**Важно:**
- Server thread — daemon, при завершении main thread убивается
- При закрытии окна pywebview → `_on_closing()` → HTTP POST /shutdown → kill subprocess → server.stop
- `os.chdir(_BASE_DIR)` выполняется в server thread — это меняет CWD для всего процесса
- `_active_proc = [None]` — list-based mutable global для отслеживания активного subprocess

---

## 5. HTTP API

### GET / или /index.html
Отдаёт `download.html` (ищет в _BIN_CANDIDATES, затем _MEIPASS, затем SCRIPT_DIR).

### GET /status
```json
{
  "phase": "idle|checking|silent_check|installing_python|installing_ytdlp|installing_ffmpeg|done|error",
  "progress": 0-100,
  "messages": [{"text": "...", "type": "info|ok|err", "time": 1234567890}],
  "python_ok": true|false,
  "ytdlp_ok": true|false,
  "server_started": true|false,
  "error": null|"error message",
  "setup_done": true|false
}
```

### GET /probe?url=URL
```json
{
  "title": "Video title",
  "duration": 123,
  "thumbnail": "https://...",
  "formats": [
    {"format_id": "137", "height": 1080, "display_label": "1080p", "filesize": 52428800, "ext": "mp4"},
    {"format_id": "136", "height": 720, "display_label": "720p", "filesize": 20971520, "ext": "mp4"}
  ],
  "audio_formats": [
    {"format_id": "140", "abr": 129.5, "filesize": 5242880, "ext": "m4a"},
    {"format_id": "251", "abr": 126.6, "filesize": 4194304, "ext": "webm"}
  ]
}
```

### GET /log?job=JOB_ID&offset=N
```json
{
  "lines": ["[yt-dlp] ...", "[download] ..."],
  "status": "running|done|error"
}
```

### GET /open-folder
Открывает папку downloads в файловом менеджере:
- Windows: `explorer <path>`
- macOS: `open <path>`
- Linux: `xdg-open <path>`

### POST /setup
Запускает setup wizard. Если уже настроено — возвращает `{"already_done": true}`.

### POST /download
```json
// Request body:
{"url": "https://youtube.com/watch?v=...", "mode": "video|audio", "format_id": "137"}

// Response (success):
{"job_id": "abc12345", "platform": "youtube"}

// Response (deps not ready):
{"deps_ready": true}  → JS повторяет запрос через 500ms

// Response (error):
{"error": "..."}
```

### POST /shutdown
Убивает активный yt-dlp subprocess (если есть), останавливает HTTP сервер.
Вызывается из app.py при закрытии окна.

---

## 6. Рабочие файлы

### 6.1. Лог файл: `instrumentarium.log`
- **Расположение:** Рядом с .exe / скриптом (`_BASE_DIR`)
- **Формат:** `%(asctime)s [%(levelname)s] %(message)s`
- **Уровень:** DEBUG
- **Нет StreamHandler** — только FileHandler (чтобы не создавать консоль на Windows)
- **Отключение:** `INSTRUMENTARIUM_LOG=0`

### 6.2. Маркёр настройки: `.setup_done`
- **Расположение:** `_BASE_DIR/.setup_done`
- **Содержимое:** Timestamp завершения настройки (`YYYY-MM-DD HH:MM:SS`)
- **Создаётся:** После успешного `run_setup()` или `_ensure_deps()`
- **Удаляется:** В начале `run_setup()` (при повторной настройке)
- **Проверяется:** При каждом запуске для определения — показывать wizard или нет

### 6.3. Lock-файл: `.instrumentarium.lock`
- **Расположение:** `_BASE_DIR/.instrumentarium.lock`
- **Механизм:** `msvcrt.locking()` (Windows) / `fcntl.flock()` (Unix)
- **Назначение:** Запуск только одного инстанса приложения
- **Освобождение:** При выходе через `atexit`

### 6.4. Папка `.bin/`
- **Расположение:** `_BASE_DIR/.bin/`
- **Содержимое:**
  - `yt-dlp.exe` / `yt-dlp` — скачивается при первом запуске
  - `ffmpeg.exe` — скачивается автоматически (Windows, BtbN builds)
  - `ffprobe.exe` — скачивается автоматически (Windows, BtbN builds)

### 6.5. Папка `downloads/`
- **Расположение:** `_BASE_DIR/downloads/`
- **Подпапки:** `youtube/`, `twitter/`, `tiktok/`, `instagram/`, `facebook/`, `linkedin/`, `other/`
- **Формат файлов:** `%(title).120s [%(id)s].%(ext)s` (ограничение 120 символов)

### 6.6. Cookies файл: `.cookies.txt`
- **Расположение:** `_BASE_DIR/.cookies.txt`
- **Назначение:** авторизация на платформах, требующих вход (LinkedIn и др.)
- **Формат:** Netscape HTTP Cookie File
- **Управление:** через диалог 🍪 Cookies в UI (drag & drop, вставка текста, очистка)
- **Использование:** yt-dlp `--cookies .cookies.txt` при каждом запросе
- **В .gitignore**: да, не коммитится

### 6.7. Папка `downloads/`
- **Расположение:** `_BASE_DIR/downloads/`
- **Подпапки:** `youtube/`, `twitter/`, `tiktok/`, `instagram/`, `facebook/`, `linkedin/`, `other/`
- **Формат файлов:** `%(title).120s [%(id)s].%(ext)s` (ограничение 120 символов)

---

## 7. Форматы видео/аудио

### 7.1. Определение видео форматов

```python
# Обрабатывает LinkedIn (vcodec=None, video_ext=mp4) и другие платформы
is_video = (vcodec != "none" and vcodec is not None) or \
           (video_ext != "none" and video_ext is not None)
```

### 7.2. Эффективное разрешение

```python
# Для вертикальных видео (Shorts 1080x1920):
is_vertical = height > width
eff_height = width if is_vertical else height  # 1080, а не 1920
```

### 7.3. Логика display_label для кнопок

| Приоритет | Условие | Label |
|-----------|---------|-------|
| 1 | `format_note` существует и не содержит "DASH" | `format_note` (например "1080p") |
| 2 | `eff_height > 0` | `"{eff_height}p"` (например "720p") |
| 3 | `format_id` существует | `format_id.upper()` (например "SD", "HD" для Facebook) |
| 4 | `video_ext` существует | `"Скачать видео"` |
| 5 | Иначе | `"Скачать видео"` |

### 7.4. Форматы скачивания

```
Видео (конкретный формат из кнопки):
  format_id+bestaudio/best → --merge-output-format mp4

Видео (авто, с ffmpeg):
  bestvideo+bestaudio/best → --merge-output-format mp4 --recode-video mp4

Видео (авто, без ffmpeg):
  best[ext=mp4]/best

Аудио:
  bestaudio[ext=m4a]/bestaudio → --extract-audio --audio-format mp3 --audio-quality 0
```

### 7.5. Дедупликация форматов

**Видео:** группировка по стандартным бакетам (144, 240, 360, 480, 720, 1080, 1440, 2160, 4320).

**Аудио:** группировка по битрейту (шаг 16kbps), сортировка по убыванию.

### 7.6. Особенности платформ

| Платформа | Особенность | Решение |
|-----------|-------------|---------|
| LinkedIn | `vcodec=None`, `video_ext=mp4` | Определение по `video_ext` |
| LinkedIn | Нет данных о разрешении | Label "Скачать видео" |
| LinkedIn | Длинные title с UTM | Обрезка до 120 символов |
| Instagram | `format_note="DASH video"` | Пропуск DASH, использование разрешения |
| Facebook | Форматы `sd`/`hd` без разрешения | Label из `format_id.upper()` |
| YouTube Shorts | Вертикальное видео 1080×1920 | `eff_height = width` → "1080p" |

---

## 8. Сборка (PyInstaller)

### 8.1. Spec-файлы

**Windows:** `video-downloader-win.spec`
- `console=False` (без консоли)
- `--onefile` (всё в один .exe)
- Включает: `app.py`, `server.py`, `download.html`, webview, cefpython3
- Иконка: `assets/icon.ico`

**Linux/macOS:** `video-downloader.spec`
- Аналогично, но без cefpython3
- Иконка: `assets/icon.png`

### 8.2. Ключевые правила для PyInstaller one-file

1. **`sys._MEIPASS`** — путь к временной папке, куда PyInstaller извлекает файлы
2. **`sys.executable`** — путь к .exe → `_BASE_DIR = dirname(sys.executable)`
3. **НИКОГДА** не использовать `subprocess.Popen([sys.executable, ...])` — fork bomb!
4. **Сервер запускается in-process** через `import server` + `threading.Thread`
5. **`os.chdir(_BASE_DIR)`** — критически важна
6. **`CREATE_NO_WINDOW`** для всех subprocess calls на Windows
7. **`sys.stdout = sys.stderr = open(os.devnull, 'w')`** — до любого импорта

### 8.3. Команды сборки

```bash
# Windows
pyinstaller video-downloader-win.spec --clean

# Linux / macOS
pyinstaller video-downloader.spec --clean
```

---

## 9. CI/CD

### Workflow: `.github/workflows/build.yml`

**Триггеры:**
- `push` в `main`
- Тег `v*` (например, `v1.0.0`)
- Ручной запуск (`workflow_dispatch`)

**Пайплайн:**

```
test (ubuntu)
  └── pip install pytest → python -m pytest tests/ -v

build (matrix: linux, windows, macos; fail-fast: false)
  └── pip install pyinstaller pywebview
  └── Windows: pip install cefpython3
  └── pyinstaller <spec> --clean --distpath dist --workpath build
  └── Архивация: tar.gz (linux/macos) или zip (windows)

release (только при теге v*)
  └── GitHub Release с тремя архивами
```

**Артефакты:**
- `Instrumentarium-linux.tar.gz` → `Instrumentarium` + `download.html`
- `Instrumentarium-windows.zip` → `Instrumentarium.exe` + `download.html`
- `Instrumentarium-macos.tar.gz` → `Instrumentarium` + `download.html`

---

## 10. Тестирование

```bash
python -m pytest tests/ -v
```

**Файл:** `tests/test_server.py` — 22 теста

**Что тестируется:**
- `detect_platform()` — 10 тестов (YouTube, Twitter, TikTok, Instagram, Facebook, LinkedIn, other, case-insensitive, empty URL, subdomains)
- `_human()` — 5 тестов (bytes, KB, MB, GB, TB)
- `find_system_python()` — 3 теста (found, not found, too old)
- `get_python_install_url()` — 2 теста (Windows 64-bit, Linux)
- `check_ytdlp()` — 2 теста (found in bin, not found)
- `/status` endpoint — 1 тест (JSON response)

**Принцип:** Тесты изолированы через mock, не зависят от сети и файловой системы.

---

## 11. Известные ограничения и планы

### ✅ Решено
- Нативное окно приложения (pywebview + CEF fallback)
- Портативность: всё в одной папке с .exe
- Setup wizard не появляется при повторном запуске
- Закрытие без зависания (daemon thread + /shutdown endpoint)
- Zombie process: /shutdown убивает активный yt-dlp subprocess
- Glow animation: progress-bar получает класс .done при завершении
- Кнопка 📁 Загрузки открывает папку с файловым менеджере
- FFmpeg auto-install (Windows, BtbN builds) + fallback без ffmpeg
- Нет консольных окон на Windows
- CI/CD для всех трёх платформ
- 22 теста, все проходят
- Single instance lock
- Автоматическая установка yt-dlp и Python
- LinkedIn: поддержка vcodec=None, video_ext=mp4
- Аудио дорожка: +bestaudio/best для всех видео форматов
- Аудио UI: битрейт (слева) + размер (справа) на кнопках
- Фиксированный размер окна 620×720 (resizable=False)
- Фиксированная позиция кнопки "Загрузки" (min-height: 120px на dl-options)
- Вертикальные видео (Shorts): корректное отображение разрешения через eff_height
- /probe endpoint: динамические кнопки форматов на основе yt-dlp
- Компактный UI: уменьшены отступы и размеры для помещения в экран
- display_label: корректные названия кнопок для всех платформ (DASH, SD/HD, разрешение)
- Ограничение длины имени файла: 120 символы для совместимости с Windows
- **Cookies система**: drag & drop / вставка cookies.txt через диалог 🍪, LinkedIn авторизация
- **?-тултипы**: CSS hover не работает в pywebview → JS `onmouseenter`/`onmouseleave`
- **Визуальный фидбек кнопок**: `transform: scale(.96)` при `:active`, блокировка кнопки во время запроса
- **Автозакрытие** cookies dialog после успешного сохранения (1.2с)

### ⬜ Планы
- Расширить тесты: HTTP-эндпоинты, setup wizard, JobLogger
- Tauri-рефакторинг (долгосрочно)

---

## Критические архитектурные паттерны

### PyInstaller one-file mode
```
Запуск .exe
  → PyInstaller извлекает всё во временную папку _MEIxxxxx
  → sys._MEIPASS = путь к _MEIPASS
  → sys.executable = путь к .exe
  → _BASE_DIR = dirname(sys.executable) = папка с .exe
  → os.chdir(_BASE_DIR) — переключаем CWD
  → Все относительные пути теперь указывают на папку с .exe
```

### Активный subprocess tracking
```python
_active_proc = [None]  # list-based mutable global

# В JobLogger.run():
_active_proc[0] = proc        # при запуске yt-dlp
# ... proc.communicate() ...
_active_proc[0] = None        # в finally блоке

# В Handler.do_POST /shutdown:
proc = _active_proc[0]
if proc and proc.poll() is None:
    proc.kill()
    proc.wait(timeout=5)
_active_proc[0] = None
```

### Платформа определяется по URL
```
youtube.com, youtu.be     → youtube
twitter.com, x.com        → twitter
tiktok.com                → tiktok
instagram.com             → instagram
facebook.com, fb.com      → facebook
linkedin.com              → linkedin
иначе                     → other
```

### Окно приложения
```
Размер: 620×720 пикселей
Resizable: False (пользователь не может менять размер)
Скролл: Контент скроллится если не помещается (overflow-y: auto)
Рендерер: edgechromium → cef → auto-detect (Windows)
          GTK/Qt (Linux), Cocoa (macOS)
```

### UI компактность
```
Card padding: 24px (было 40px)
Header: 1.2rem (было 1.4rem)
Subtitle margin-bottom: 16px (было 28px)
Setup icon: 2.5rem (было 3.5rem)
URL input padding: 10px 14px (было 12px 16px)
Mode toggle padding: 10px (было 14px)
dl-options min-height: 120px (было 170px)
res-btn padding: 12px 16px (было 14px 20px)
big-downloads-btn margin-top: 12px (было 20px)
```

---

*Последнее обновление: 2026-05-30*
