# INSTRUMENTARIUM — Project Context

*Этот файл — наш рабочий контекст. Изучаем перед началом работы, обновляем после завершения.*

## Последнее обновление: 2026-05-31 (вечер)

---

## Что это за проект

**Instrumentarium** — десктопный portable-инструмент для скачивания видео с YouTube, Twitter/X, TikTok, Instagram, Facebook, LinkedIn и 1000+ других сайтов.

**Ключевой принцип:** Распаковал запустил вставил ссылку скачал. Без установщиков, без командной строки, без настройки. Всё в одной папке.

**Статус:** Рабочий MVP. CI/CD полностью настроен. Portable-билды для всех трёх платформ. Активная итерация: баги и улучшения по результатам тестирования.

**Технологический стек:**
- Python 3.7+ (встроенный в билд)
- yt-dlp (скачивается автоматически)
- pywebview + cefpython3 (нативное окно)
- PyInstaller (standalone-бинарь)
- pytest (22 теста)

---

## Архитектура

### Структура файлов

```
instrumentarium/
├── app.py                      # Десктоп-лаунчер (pywebview, сервер in-process)
├── server.py                   # Backend: setup wizard + HTTP server + yt-dlp
├── download.html               # UI: setup wizard + загрузчик (тёмная тема, русский)
├── start.sh / start.bat        # Быстрый запуск без сборки
├── assets/
│   ├── icon.svg / .png / .ico # Иконки (в git)
│   └── icon_build.py           # Утилита SVG → .ico/.png
├── tests/test_server.py        # 22 теста (pytest)
├── video-downloader.spec       # PyInstaller spec (Linux/macOS)
├── video-downloader-win.spec   # PyInstaller spec (Windows)
├── pytest.ini                  # Конфиг pytest
├── .github/workflows/build.yml # CI/CD
├── BUILD.md                    # Полная архитектурная документация
├── README.md                   # Описание проекта
└── downloads/                  # Создаётся автоматически
```

### Принципиальная схема потоков

```
Main Thread (app.py)
  ├── pywebview event loop (блокирует main thread)
  │    При закрытии → HTTP POST /shutdown → kill subprocess → stop server
  │
  └── Server Thread (daemon, _start_server_in_thread)
        ├── import server
        ├── os.chdir(_BASE_DIR)
        ├── if .setup_done → phase="silent_check", _ensure_deps() in bg thread
        ├── if !.setup_done → run_setup() in bg thread (wizard)
        └── HTTP server на 0.0.0.0:18765 (serve_forever, timeout=0.5)
              │
              ├── Setup Thread (daemon): run_setup() или _ensure_deps()
              └── JobLogger Thread (daemon): subprocess yt-dlp → parse stdout
```

### Портативность: всё в одной папке

**`_BASE_DIR`** = папка с .exe (PyInstaller: `dirname(sys.executable)`, dev: `dirname(__file__)`)

Все рабочие файлы ТОЛЬКО в `_BASE_DIR`:
```
_BASE_DIR/
├── instrumentarium.log         # Лог приложения (debug level)
├── .setup_done                 # Маркёр: настройка завершена (timestamp)
├── .instrumentarium.lock       # Lock: один инстанс
├── .bin/
│   ├── yt-dlp.exe              # Скачивается при первом запуске
│   └── ffmpeg.exe              # Скачивается автоматически (Windows)
│   └── ffprobe.exe             # Скачивается автоматически (Windows)
└── downloads/
    ├── youtube/                # Скачанные файлы по платформам
    ├── twitter/
    ├── tiktok/
    ├── instagram/
    ├── facebook/
    ├── linkedin/
    └── other/
```

**Ничего не пишется в AppData, ~/.instrumentarium, или куда-либо ещё.**

### Ключевые технические решения

- **pywebview** — нативное окно приложения (не вкладка браузера)
  - Windows: edgechromium (WebView2) → cef (Chromium Embedded) → auto fallback
  - Linux: GTK/Qt, macOS: Cocoa
  - Окно НЕизменяемого размера (resizable=False), 620×720
- **yt-dlp** скачивается автоматически в `.bin/` при первом запуске
- **ffmpeg** скачивается автоматически на Windows (BtbN builds)
- **Python** на Windows устанавливается автоматически (silent install, PrependPath)
- **Логирование:** только в файл (`instrumentarium.log`), без StreamHandler
- **Один инстанс:** lock-файл через msvcrt.locking (Win) / fcntl.flock (Unix)
- **Setup marker:** `.setup_done` — при повторном запуске wizard пропускается
- **Shutdown:** `POST /shutdown` → kill active yt-dlp → server.stop → daemon threads die
- **Active process tracking:** `_active_proc = [None]` — list-based mutable global

---

## HTTP API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/`, `/index.html` | Отдаёт download.html |
| GET | `/status` | JSON: setup_state (phase, progress, messages, setup_done) |
| GET | `/log?job=ID&offset=N` | JSON: {lines, status} — логи скачивания |
| GET | `/probe?url=URL` | JSON: {title, duration, thumbnail, formats, audio_formats} |
| GET | `/open-folder` | Открывает папку downloads в файловом менеджере |
| POST | `/setup` | Запускает setup wizard |
| POST | `/download` | Запускает скачивание {url, mode, format_id} → {job_id, platform} |
| POST | `/shutdown` | Убивает активный subprocess, останавливает сервер |

---

## UI: download.html

Два экрана + диалог cookies:

### Setup screen (первый запуск)
- Кнопка "🚀 Настроить и запустить"
- Прогресс-бар с shimmer-анимацией
- Автоматический переход на Download screen после завершения

### Download screen (после настройки)
- **Заголовок** "🎬 Video Downloader"
- Поле ввода URL с auto-detect платформы
- Бейдж платформы (🔴 YouTube, 🐦 Twitter/X, 🎵 TikTok, 📸 Instagram, 📘 Facebook, 💼 LinkedIn, 🌐 Другое)
- Переключатель 🎥 Видео (MP4) / 🎵 Аудио (MP3)
- **Кнопки видео**: динамические, на основе /probe. Показывают разрешение (1080p, 720p), размер файла и расширение
- **Кнопки аудио**: динамические, на основе /probe. Показывают битрейт (130kbps) слева и размер (3.3 MB · M4A) справа
- Контейнер `dl-options` с `min-height: 170px` — фиксированное место для кнопок, окно не прыгает
- Прогресс-бар: shimmer во время загрузки, зелёный `.done` при завершении
- Toast для ошибок (❌ + описание + hint "Подробности в instrumentarium.log")
- **Кнопка "📁 Загрузки"** внизу → `GET /open-folder`
- **Футер**: ссылка "🍪 Cookies" с ?-тултипом (при наведении — подсказка о приватных страницах)

### Cookies Dialog (🍪)
- **Drag & drop зона** — перетаскивание файла cookies.txt или клик для выбора через `<input type="file">`
- **textarea** — для ручной вставки содержимого cookies.txt
- **?-тултип** в конце текста "Как получить cookies.txt ?" — при наведении всплывает инструкция:
  - Установить расширение "Get cookies.txt LOCALLY" → linkedin.com → Export
- **Кнопки**: Отмена, Очистить, Сохранить
- **Сохранить**: блокирует кнопку на время запроса, показывает "⏳ Сохраняю…" → "✅ Готово" → автозакрытие через 1.2с
- **Очистить**: очищает cookies на сервере и textarea
- Cookies сохраняются в `.cookies.txt` рядом с .exe, используются yt-dlp для авторизации на LinkedIn
- **pywebview нюанс**: CSS `:hover` не работает на вложенных элементах — тултипы через JS `onmouseenter`/`onmouseleave`

### Формат раздела /probe

`/probe` возвращает два массива:
- **formats** — видео форматы с полями: format_id, height, display_label, filesize, ext
  - LinkedIn: vcodec=None, video_ext=mp4 → определяется как видео
  - Вертикальные видео (Shorts): eff_height = width (реальная разрешение)
  - Дедупликация по стандартным бакетам (144, 240, 360, 480, 720, 1080, 1440, 2160)
- **audio_formats** — аудио форматы с полями: format_id, abr, filesize, ext
  - Дедупликация по битрейту (шаг 16kbps)
  - Сортировка по убыванию битрейта

### JS Bootstrap
```javascript
fetch('/status').then(d => {
  if (d.setup_done || d.phase === 'silent_check' || d.phase === 'checking') {
    showDownloadScreen();
  }
  // иначе показать setup screen (первый запуск)
});
```

---

## Сборка и CI/CD

### Быстрый запуск (без сборки)
- Windows: `start.bat`
- Linux/macOS/WSL: `bash start.sh`

### PyInstaller
- Windows: `pyinstaller video-downloader-win.spec --clean`
- Linux/macOS: `pyinstaller video-downloader.spec --clean`

### CI/CD (GitHub Actions)
Пуш в main или тег v*:
1. **test** (ubuntu) — pytest
2. **build** (matrix linux/windows/macos, fail-fast: false) — PyInstaller → portable архив
3. **release** (только v*) — GitHub Release

Артефакты:
- `Instrumentarium-linux.tar.gz`
- `Instrumentarium-windows.zip`
- `Instrumentarium-macos.tar.gz`

---

## Тестирование

```bash
python -m pytest tests/ -v
```

22 теста: detect_platform (10), _human (5), find_system_python (3), get_python_install_url (2), check_ytdlp (2), status_endpoint (1)

---

## Известные ограничения / возможные доработки

### ✅ Решено
- Нативное окно приложения (pywebview + CEF fallback)
- Портативность: всё в одной папке с .exe (не AppData)
- Setup wizard не появляется при повторном запуске (.setup_done)
- Закрытие без зависания (daemon thread + /shutdown endpoint)
- Zombie process: /shutdown убивает активный yt-dlp subprocess
- Glow animation: progress-bar получает класс .done (зелёный, без shimmer)
- Кнопка 📁 Загрузки открывает папку с файловым менеджере
- FFmpeg auto-install (Windows, BtbN builds)
- Нет консольных окон на Windows (CREATE_NO_WINDOW, devnull stdout)
- CI/CD для всех трёх платформ
- 22 теста, все проходят
- Lock-файл (один инстанс)
- LinkedIn видео: поддержка vcodec=None, video_ext=mp4
- Аудио дорожка: +bestaudio/best в формате скачивания
- Аудио UI: битрейт + размер на кнопках
- Фиксированный размер окна (620×720, resizable=False)
- Фиксированная позиция кнопки "Загрузки" (min-height на dl-options)
- Вертикальные видео (Shorts): корректное отображение разрешения

- **Cookies система**: drag & drop / вставка cookies.txt, LinkedIn авторизация, автозакрытие диалога
- **?-тултипы**: JS onmouseenter/onmouseleave (CSS hover не работает в pywebview)
- **Визуальный фидбек кнопок**: scale(.96) при :active, блокировка во время запроса

### ⚠️ macOS — известные проблемы (требуют решения)

CI собирает бинарник для macOS, но есть **5 нерешённых проблем**, блокирующих полноценную работу:

**1. Gatekeeper / неподписанное приложение (КРИТИЧНО)**
- GitHub Actions артефакт не подписан и не нотаризован
- При первом запуске macOS заблокирует: *"не может быть открыто, так как Apple не может проверить наличие вредоносного ПО"*
- Обходной путь для пользователя: «Открыть всё равно» в System Preferences → Security, или `xattr -cr /path/to/Instrumentarium`
- Решение: codesign + notarize в CI (дорого, нужен Apple Developer Account $99/yr) ИЛИ инструкция для пользователя

**2. Нет .app bundle**
- Сейчас сборка — голый бинарник `Instrumentarium`
- macOS пользователи ожидают `Instrumentarium.app` (Dock, иконка, Info.plist)
- Без .app: нет иконки в Dock, нет привычного двойного клика
- Решение: собрать .app структуру в spec файле или post-build скриптом

**3. ffmpeg не скачивается (в отличие от Windows)**
- На macOS только инструкция `brew install ffmpeg` — нет авто-загрузки
- Без ffmpeg: нет объединения видео+аудио, нет конвертации в mp3
- Решение: скачать ffmpeg бинарник (например из evermeet.cx или static builds) при первом запуске

**4. Python установка (.pkg нуждается в правах)**
- Скачивается `python-3.12.9-macos11.pkg` (macOS 11+)
- Установка требует системные права + подтверждение в Security
- Решение: проверить наличие Homebrew Python или предложить `brew install python3`

**5. pywebview рендерер на macOS**
- `app.py` использует рендереры `["edgechromium", "cef"]` только для Windows; на macOS — auto-detect (Cocoa/WebKit)
- Cocoa WebView может иметь ограничения по сравнению с CEF (CSS hover и т.д.)
- Нужно тестирование: тултипы, drag & drop, cookies dialog

**Приоритет:** Gatekeeper (1) → .app bundle (2) → ffmpeg (3) → остальное

### ⬜ Планы
- Расширить тесты: HTTP-эндпоинты, setup wizard, JobLogger
- Tauri-рефакторинг (долгосрочно)

---

## Git

- Репозиторий: `songarf/instrumentarium`
- Remote: `git@github.com:songarf/instrumentarium.git`
- Ветка: `main`

---

## Доступы

- **GitHub Actions API:** токен в `/opt/data/auth.json` → `credential_pool.github[0].access_token`

---

## Релизы

Портативные билды привязаны к тегам `v*`. При создании тега: тесты → билды → GitHub Release.

---

## Критические архитектурные паттерны

### PyInstaller one-file правила
1. `sys._MEIPASS` — временная папка с извлечёнными файлами
2. `sys.executable` — путь к .exe → `_BASE_DIR = dirname(sys.executable)`
3. **НИКОГДА** `subprocess.Popen([sys.executable, ...])` — fork bomb!
4. Сервер in-process через `import server` + `threading.Thread`
5. `os.chdir(_BASE_DIR)` в server thread
6. `CREATE_NO_WINDOW` для всех subprocess calls на Windows
7. `sys.stdout = sys.stderr = devnull` до любого импорта

### Активный subprocess tracking
```python
_active_proc = [None]  # list-based mutable global, no 'global' keyword needed
# JobLogger:
_active_proc[0] = proc  # при запуске
_active_proc[0] = None  # при завершении (finally)
# /shutdown:
if _active_proc[0] and _active_proc[0].poll() is None:
    _active_proc[0].kill()
```

### Форматы видео/аудио
```
Видео (формат кнопки): format_id+bestaudio/best → merge → mp4
Видео (авто, с ffmpeg): bestvideo+bestaudio/best → merge + recode → mp4
Видео (авто, без ffmpeg): best[ext=mp4]/best
Аудио:                    bestaudio[ext=m4a]/bestaudio → extract → mp3
```

### Определение видео форматов
```python
# LinkedIn и другие платформы с vcodec=None:
is_video = (vcodec != "none" and vcodec is not None) or (video_ext != "none" and video_ext is not None)
```

### Эффективное разрешение для вертикальных видео
```python
# Shorts (1080x1920): height=1920, width=1080 → eff_height=1080
is_vertical = height > width
eff_height = width if is_vertical else height
```

---

## Контекст обсуждений

> **2026-05-31:** Добавлена система cookies для LinkedIn и других приватных платформ. Drag & drop загрузка cookies.txt, ?-тултипы с инструкциями, автозакрытие диалога после сохранения. Исправлены баги: CSS hover не работал в pywebview (заменён на JS onmouseenter), кнопка «Сохранить» не имела визуального фидбека. Коммит `4a970be`.

> **2026-05-31 (позже):** Добавлен маппинг ошибок yt-dlp в понятные сообщения на русском (`_map_ytdlp_error`). Unsupported URL, private video, 404, geo-blocked, rate-limited, network errors — всё обрабатывается. JS showError() теперь принимает null message. Коммит `4828231`. Обнаружены 5 проблем macOS-сборки (Gatekeeper, нет .app, ffmpeg, Python .pkg, pywebview Cocoa) — задокументированы в CONTEXT.md как отдельная секция. Коммит `cabf2d5`.

> **2026-05-30:** Исправлены 5 проблем по результатам тестирования пользователя: (1) LinkedIn видео не определялись — исправлен фильтр is_video для обработки vcodec=None. (2) Все видео скачивались без звука — добавлен +bestaudio/best в формат. (3) Аудио секция показывала "Скачать MP3" — теперь показывает битрейт и размер. (4) Окно можно было растягивать — установлено resizable=False. (5) Кнопка "Загрузки" прыгала — добавлен min-height: 170px на dl-options. Также исправлен JS баг: uniqueFormats → probedFormats. Все изменения протестированы: LinkedIn probe OK, видео+аудио 确认 (h264+aac), pytest 22/22.

> **2026-05-29:** Исправлены 3 бага: Zombie process, shimmer после загрузки, кнопка 📁 Загрузки. Коммит `3bd7cdc`.

> **2026-05-29 (ранее):** yt-dlp падал на `--embed-metadata` без ffmpeg. Исправлено. Коммит `204d8b9`.

> **2026-05-29 (ранее):** Переход на pywebview + CEF. Коммит `1bdf38d`.

> **2026-05-28:** download.html не находился в билде. Коммит `1acf0cf`.

> **2026-05-27:** Setup screen при повторном запуске, консоли на Windows. Коммит `4f03fed`.

> **2026-05-26:** Fork bomb. Решение: сервер in-process.

> **2026-05-25:** Переименование → Instrumentarium. CI исправлен.

> **2026-05-24:** Иконка, тесты, CI.

---

*ОМ. РА. СИАННА. ТАУ.*
