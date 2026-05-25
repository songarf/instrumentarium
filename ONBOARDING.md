# INSTRUMENTARIUM — Onboarding Guide

*Файл для быстрого погружения. Читать в указанном порядке.*

---

## Как начать работу

**Порядок чтения для полного понимания проекта:**

### Шаг 1: Обзор проекта (5 минут)
**`README.md`** — что это за проект, зачем, основные ссылки

### Шаг 2: Техническая картина (15 минут)
**`SPEC.md`** — полная техническая спецификация:
- Функциональные требования (что делает приложение)
- Технические требования (зависимости, системные требования)
- Архитектура (компоненты, потоки, API)
- Поддерживаемые платформы и форматы
- Ограничения и планы

### Шаг 3: Архитектура кодовой базы (15 минут)
**`BUILD.md`** — как устроен код:
- Структура файлов
- Потоки (threads) и их взаимодействие
- HTTP API (эндпоинты, форматы запросов/ответов)
- Рабочие файлы (логи, маркёры, lock)
- Форматы видео/аудио и логика display_label
- Сборка (PyInstaller, CI/CD)
- Критические архитектурные паттерны

### Шаг 4: Пользовательский опыт (5 минут)
**`USER_GUIDE.md`** — как пользователь взаимодействует с приложением:
- Первый запуск
- Скачивание видео/аудио
- Где файлы
- Решение проблем

### Шаг 5: Текущий контекст (5 минут)
**`CONTEXT.md`** — внутренний документ с актуальным прогрессом:
- Что сделано
- Что в процессе
- История изменений
- Известные баги и планы

---

## Файловая структура

```
instrumentarium/
│
├── 📄 Документация
│   ├── README.md              # Обзор проекта
│   ├── SPEC.md                # Техническая спецификация
│   ├── BUILD.md               # Архитектура кодовой базы
│   ├── USER_GUIDE.md          # Руководство пользователя
│   ├── CONTEXT.md             # Внутренний контекст (в .gitignore)
│   └── ONBOARDING.md          # Этот файл
│
├── 🔧 Исходный код
│   ├── app.py                 # Точка входа: pywebview, сервер, окно
│   ├── server.py              # Backend: setup, HTTP API, yt-dlp
│   └── download.html          # UI: setup screen + download screen
│
├── 🚀 Запуск
│   ├── start.sh               # Linux/macOS/WSL
│   └── start.bat              # Windows
│
├── 📦 Сборка
│   ├── video-downloader.spec       # PyInstaller spec (Linux/Mac)
│   ├── video-downloader-win.spec   # PyInstaller spec (Windows)
│   └── .github/workflows/build.yml # CI/CD
│
├── 🧪 Тесты
│   ├── tests/test_server.py   # 22 теста (pytest)
│   └── pytest.ini             # Конфиг pytest
│
├── 🎨 Ассеты
│   ├── assets/icon.svg        # Иконка (вектор)
│   ├── assets/icon.png        # Иконка 512×512
│   ├── assets/icon.ico        # Иконка Windows
│   └── assets/icon_build.py   # Утилита SVG → .ico/.png
│
└── 📁 Игнорируемые (не в git)
    ├── downloads/             # Скачанные видео
    ├── .bin/                  # yt-dlp, ffmpeg
    ├── .setup_done            # Маркёр настройки
    ├── .instrumentarium.lock  # Lock-файл
    └── instrumentarium.log    # Лог
```

---

## Ключевые файлы кода

### `app.py` — Точка входа
- Настройка stdout/stderr → devnull (Windows)
- Вычисление `_BASE_DIR`
- Single-instance lock
- Запуск сервера в daemon thread
- Открытие окна pywebview (620×720, resizable=False)
- Обработка закрытия окна → `/shutdown`

### `server.py` — Backend (~1040 строк)
- **Setup wizard**: `run_setup()`, `_ensure_deps()`
- **HTTP Handler**: `/status`, `/probe`, `/download`, `/setup`, `/shutdown`, `/log`, `/open-folder`
- **Probe logic**: парсинг форматов yt-dlp, определение `display_label`, дедупликация
- **Download logic**: `JobLogger` thread, subprocess yt-dlp, парсинг stdout
- **Форматы**: `format_id+bestaudio/best` для видео, `bestaudio` → MP3 для аудио

### `download.html` — UI (~720 строк)
- **Setup screen**: кнопка, прогресс-бар
- **Download screen**: URL input, бейдж платформы, mode toggle, кнопки форматов
- **JS**: `doProbe()`, `renderResButtons()`, `startDownload()`, `startDownloadAudio()`
- **CSS**: тёмная тема, компактные размеры

---

## Быстрый старт разработки

### 1. Прочитать документацию (в порядке выше)

### 2. Запустить локально
```bash
cd /opt/workspace/projects/instrumentarium
bash start.sh
```

### 3. Внести изменения

### 4. Протестировать
```bash
python -m pytest tests/ -v
```

### 5. Собрать билд
```bash
# Linux
pyinstaller video-downloader.spec --clean

# Windows
pyinstaller video-downloader-win.spec --clean
```

### 6. Закоммитить и пушнуть
```bash
git add -A
git commit -m "описание изменений"
git push origin main
```

---

## Важные правила

1. **Всё в одной папке** — никаких путей в AppData, ~/.instrumentarium и т.д.
2. **Сервер in-process** — никогда `subprocess.Popen([sys.executable, ...])` (fork bomb!)
3. **yt-dlp скачивается автоматически** — не бандлить в билд
4. **ffmpeg скачивается на Windows** — BtbN builds
5. **Один инстанс** — lock-файл
6. **Корректное закрытие** — `/shutdown` → kill subprocess → stop server
7. **Имя файла ≤ 120 символов** — для совместимости с Windows
8. **Аудио всегда с видео** — `+bestaudio/best`
9. **display_label приоритет** — format_note → eff_height → format_id → "Скачать видео"
10. **Вертикальные видео** — `eff_height = width` для Shorts/Reels

---

## Контекст текущей сессии

*Последнее обновление: 2026-05-30*

### Что сделано
- Рабочий MVP: скачивание видео/аудио с 6+ платформ
- Setup wizard с автоматической установкой зависимостей
- Динамические кнопки форматов на основе yt-dlp probe
- Компактный UI (620×720, помещается в экран)
- CI/CD для трёх платформ
- 22 теста

### Что в процессе
- Тестирование на Windows (баги с длинными именами файлов исправлены)
- Улучшение display_label для разных платформ

### Известные проблемы
- Без ffmpeg качество видео ограничено (DASH-потоки не мержатся)
- Нет очереди загрузок
- Нет паузы/отмены

---

*Этот файл читать первым при начале новой сессии разработки.*
