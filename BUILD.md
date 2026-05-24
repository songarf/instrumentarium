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
7. [Сборка (PyInstaller)](#7-сборка-pyinstaller)
8. [CI/CD](#8-cicd)
9. [Тестирование](#9-тестирование)
10. [Известные ограничения и планы](#10-известные-ограничения-и-планы)

---

## 1. Что это за приложение

**Instrumentarium** — портативное десктопное приложение для скачивания видео с YouTube, Twitter/X, TikTok, Instagram, Facebook, LinkedIn и 1000+ других сайтов.

**Ключевой принцип:** Распаковал → запустил → вставил ссылку → скачал. Без установщиков, без командной строки, без настройки. Всё в одной папке.

**Целевые платформы:** Windows, Linux, macOS

**Технологический стек:**
- Python 3.7+ (встроенный в билд)
- yt-dlp (скачивается автоматически при первом запуске)
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
├── README.md                   # Описание проекта для GitHub
└── downloads/                  # ← Создаётся автоматически (папка платформ)
```

### Файлы, генерируемые при работе (все в папке с .exe):

```
<папка с .exe>/
├── instrumentarium.log         # Лог приложения (debug level)
├── .setup_done                 # Маркёр завершённой настройки (содержит timestamp)
├── .instrumentarium.lock       # Lock-файл для единственного инстанса
├── .bin/                       # Скачанные бинарники
│   ├── yt-dlp.exe              # (Windows) или yt-dlp (Linux/macOS)
│   └── ffmpeg.exe              # (опционально, если найден/скачан)
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
  │       └── HTTP server на 0.0.0.0:18765
  │
  ├── 6. Ожидание готовности сервера (max 5s, polling 127.0.0.1:18765)
  │
  └── 7. Открытие окна pywebview:
          Windows: edgechromium → cef → auto-detect
          Linux:   auto-detect (GTK/Qt)
          macOS:   auto-detect (Cocoa)
          При закрытии окна → srv.shutdown()
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
  │             installing_ytdlp | done | error
  │     progress: 0-100
  │     messages: [{text, type, time}]
  │     python_ok, ytdlp_ok, server_started, error
  │
  ├── HTTP Handler:
  │     GET  /           → download.html
  │     GET  /status     → JSON setup_state
  │     GET  /log?job=&offset= → JSON {lines, status}
  │     POST /setup      → запустить setup wizard
  │     POST /download   → запустить скачивание
  │
  ├── Setup flow:
  │     run_setup() — полный wizard (первый запуск):
  │       1. find_system_python()
  │       2. check_ytdlp() / install_ytdlp()
  │       3. _write_marker()
  │
  │     _ensure_deps() — тихая проверка (повторный запуск):
  │       1. find_system_python()
  │       2. check_ytdlp() / install_ytdlp()
  │       3. _write_marker()
  │       4. phase = "done"
  │
  └── Download:
        JobLogger (thread):
          1. Найти yt-dlp в _BIN_CANDIDATES
          2. Найти ffmpeg
          3. Сформировать cmd с форматами
          4. _popen(cmd) → парсить stdout
          5. Обновлять download_jobs[jid]
```

### 3.3. UI: download.html

Одностраничный HTML с двумя экранами:

**Setup screen** (показывается при первом запуске):
- Кнопка "🚀 Настроить и запустить"
- Прогресс-бар с процентами и статусом
- После завершения → переключение на Download screen

**Download screen** (показывается всегда после настройки):
- Поле ввода URL
- Бейдж платформы (определяется по URL)
- Переключатель Видео/Аудио
- Кнопка "⬇️ Скачать"
- Прогресс-бар скачивания
- Toast для ошибок

**Bootstrap-логика (выполняется при загрузке HTML):**
```javascript
fetch('/status').then(d => {
  if (d.setup_done || d.phase === 'silent_check' || d.phase === 'checking') {
    // Уже настроено — показать download screen сразу
    showDownloadScreen();
  }
  // Иначе показать setup screen (первый запуск)
});
```

---

## 4. Потоки (Threads)

```
Main Thread (app.py)
  └── pywebview event loop (блокирует main thread)

Server Thread (daemon, app.py → _start_server_in_thread)
  └── http.server.HTTPServer.serve_forever()
        └── Handler.do_GET/do_POST (вызывается из HTTP-потока сервера)

Setup Thread (daemon, server.py → run_setup или _ensure_deps)
  └── Проверка/установка Python, yt-dlp

Download Thread (daemon, server.py → JobLogger)
  └── subprocess.Popen(yt-dlp) → парсинг stdout
```

**Важно:**
- Server thread — daemon, при завершении main thread убивается
- При закрытии окна pywebview → `_on_closing()` → `srv.shutdown()` → сервер останавливается
- `os.chdir(_BASE_DIR)` выполняется в server thread — это меняет CWD для всего процесса

---

## 5. HTTP API

### GET / или /index.html
Отдаёт `download.html` (ищет в _BIN_CANDIDATES, затем _MEIPASS, затем SCRIPT_DIR).

### GET /status
```json
{
  "phase": "idle|checking|silent_check|installing_python|installing_ytdlp|done|error",
  "progress": 0-100,
  "messages": [{"text": "...", "type": "info|ok|err", "time": 1234567890}],
  "python_ok": true|false,
  "ytdlp_ok": true|false,
  "server_started": true|false,
  "error": null|"error message",
  "setup_done": true|false
}
```

### GET /log?job=JOB_ID&offset=N
```json
{
  "lines": ["[yt-dlp] ...", "[download] ..."],
  "status": "running|done|error"
}
```

### POST /setup
Запускает setup wizard. Если уже настроено — возвращает `{"already_done": true}`.

### POST /download
```json
// Request body:
{"url": "https://youtube.com/watch?v=...", "mode": "video|audio"}

// Response (success):
{"job_id": "abc12345", "platform": "youtube"}

// Response (deps not ready):
{"deps_ready": true}  → JS повторяет запрос через 500ms

// Response (error):
{"error": "..."}
```

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
- **Содержимое:** `yt-dlp.exe` (скачивается при первом запуске)
- **Альтернативные пути:** `_EXE_DIR/.bin/`, `_MEIPASS/.bin/` (для PyInstaller)

### 6.5. Папка `downloads/`
- **Расположение:** `_BASE_DIR/downloads/`
- **Подпапки:** `youtube/`, `twitter/`, `tiktok/`, `instagram/`, `facebook/`, `linkedin/`, `other/`
- **Формат файлов:** `%(title)s [%(id)s].%(ext)s`

---

## 7. Сборка (PyInstaller)

### 7.1. Spec-файлы

**Windows:** `video-downloader-win.spec`
- `console=False` (без консоли)
- `--onefile` (всё в один .exe)
- Включает: `app.py`, `server.py`, `download.html`, webview, cefpython3
- Иконка: `assets/icon.ico`

**Linux/macOS:** `video-downloader.spec`
- Аналогично, но без cefpython3
- Иконка: `assets/icon.png`

### 7.2. Ключевые правила для PyInstaller one-file

1. **`sys._MEIPASS`** — путь к временной папке, куда PyInstaller извлекает файлы. Используется для поиска `download.html` и `.bin/`.

2. **`sys.executable`** — путь к .exe (не к скрипту!). Используется для `_BASE_DIR`.

3. **Никогда** не использовать `subprocess.Popen([sys.executable, ...])` — это запустит ещё один .exe, который запустит ещё один → fork bomb.

4. **Сервер запускается in-process** через `import server` + `threading.Thread`, а не через subprocess.

5. **`os.chdir(_BASE_DIR)`** — критически важна, иначе относительные пути укажут не туда.

6. **`CREATE_NO_WINDOW`** для всех subprocess calls на Windows.

7. **`sys.stdout = sys.stderr = open(os.devnull, 'w')`** — до любого импорта, чтобы предотвратить создание консоли.

### 7.3. Команды сборки

```bash
# Windows
pyinstaller video-downloader-win.spec --clean

# Linux / macOS
pyinstaller video-downloader.spec --clean
```

Результат: `dist/Instrumentarium` (или `dist/Instrumentarium.exe`)

---

## 8. CI/CD

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

## 9. Тестирование

```bash
python -m pytest tests/ -v
```

**Файл:** `tests/test_server.py` — 22 теста

**Что тестируется:**
- `detect_platform()` — 10 тестов (YouTube, Twitter, TikTok, Instagram, Facebook, LinkedIn, other, case-insensitive, empty)
- `_human()` — 5 тестов (bytes, KB, MB, GB, TB)
- `find_system_python()` — 3 теста (found, not found, too old)
- `get_python_install_url()` — 2 теста (Windows 64-bit, Linux)
- `check_ytdlp()` — 2 теста (found in bin, not found)
- `/status` endpoint — 1 тест (JSON response)

**Принцип:** Тесты изолированы через mock, не зависят от сети и файловой системы.

---

## 10. Известные ограничения и планы

### ✅ Решено
- Нативное окно приложения (pywebview + CEF fallback)
- Мерцание setup wizard при повторном запуске
- Логирование в файл
- Скачивание при повторном запуске (ожидание deps)
- Все файлы в одной папке
- Single instance lock
- Автоматическая установка yt-dlp
- Автоматическая установка Python (Windows)
- CI/CD для всех трёх платформ

### ⬜ Планы
- Расширить тесты: HTTP-эндпоинты, setup wizard, JobLogger
- Полный перевод UI на русский
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

### Форматы видео/аудио
```
Видео (с ffmpeg):  bestvideo[ext=mp4]+bestaudio[ext=m4a] → merge → mp4
Видео (без ffmpeg): best[ext=mp4]/best
Аудио:               bestaudio → extract → mp3
```

### Метаданные
- `--embed-metadata` — встраивает метаданные в файл
- `--embed-thumbnail` — встраивает превью

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

---

*Последнее обновление: 2026-05-28*
