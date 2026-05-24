# INSTRUMENTARIUM — Build Instructions

*Как собрать Instrumentarium на разных платформах.*

---

## Содержание

1. [Быстрый запуск (без сборки)](#быстрый-запуск)
2. [Локальная сборка](#локальная-сборка)
3. [CI/CD](#cicd)
4. [Структура артефактов](#структура-артефактов)
5. [Устранение неполадок](#устранение-неполадок)

---

## Быстрый запуск

Для разработки и тестирования без сборки:

```bash
# Linux / macOS / WSL
bash start.sh

# Windows
start.bat
```

Требования: Python 3.7+, pip

---

## Локальная сборка

### Требования

- Python 3.12
- pip
- PyInstaller (`pip install pyinstaller`)

### Linux

```bash
pip install pyinstaller
pyinstaller video-downloader.spec --clean
# Результат: dist/Instrumentarium
```

### Windows

```cmd
pip install pyinstaller
pyinstaller video-downloader-win.spec --clean
# Результат: dist/Instrumentarium.exe
```

### macOS

```bash
pip install pyinstaller
pyinstaller video-downloader.spec --clean
# Результат: dist/Instrumentarium
```

### Флаги PyInstaller

| Флаг | Назначение |
|------|-----------|
| `--onefile` | Всё в один исполняемый файл |
| `--console` / `--noconsole` | Показывать/скрыть консоль (Windows) |
| `--clean` | Очистить кеш PyInstaller перед сборкой |
| `--distpath` | Куда положить результат |
| `--workpath` | Куда положить временные файлы |

---

## CI/CD

GitHub Actions автоматически собирает при каждом push в `main`.

### Триггеры

- `push` в ветку `main`
- Тег `v*` (например, `v1.0.0`)
- Ручной запуск (`workflow_dispatch`)

### Пайплайн

```
test (ubuntu)
  ↓ pytest 22 tests
build (matrix)
  ↓ linux  → tar gz (Instrumentarium + download.html)
  ↓ windows → zip (Instrumentarium.exe + download.html)
  ↓ macOS   → tar gz (Instrumentarium + download.html)
release (только при теге v*)
  → GitHub Release с тремя архивами
```

### CI особенности

- `--clean` флаг обходит кеширование PyInstaller (issue #7653)
- Очистка `bincache` перед каждым билдом
- Архивируются ВСЕ файлы из `dist/` (wildcard `*`)

---

## Структура артефактов

Каждый архив содержит бинарь + UI-файл:

```
Instrumentarium-linux.tar.gz
  └── Instrumentarium      # исполняемый файл
  └── download.html        # UI

Instrumentarium-windows.zip
  └── Instrumentarium.exe  # исполняемый файл
  └── download.html        # UI

Instrumentarium-macos.tar.gz
  └── Instrumentarium      # исполняемый файл
  └── download.html        # UI
```

### Важно: download.html

`download.html` — это UI приложения. Он должен лежать **рядом** с бинарником. При запуске сервер ищет его в:
1. Папке с бинарником
2. PyInstaller `_MEIPASS` (временная папка one-file mode)
3. Папке `server.py` (dev mode)

---

## Тестирование билда

### Чеклист после сборки

- [ ] При первом запуске показывается setup wizard
- [ ] Setup wizard проверяет/скачивает зависимости
- [ ] После setup появляется экран загрузки
- [ ] При повторном запуске setup НЕ показывается
- [ ] Вставка ссылки → определяется платформа
- [ ] Скачивание видео работает
- [ ] Нет консольных окон (Windows)

### Логи

Логи пишутся в:
```
Windows: %LOCALAPPDATA%\Instrumentarium\instrumentarium.log
Linux:   ~/.instrumentarium/instrumentarium.log
```

---

## Устранение неполадок

### "UI file not found"

`download.html` не найден. Убедитесь что он лежит рядом с .exe.

### "ERR_EMPTY_RESPONSE" / страница не открывается

Сервер не запустился. Проверьте `instrumentarium.log`.

### "Another instance is already running"

Предыдущий инстанс не закрылся. Удалите lock-файл:
```
Windows: %LOCALAPPDATA%\Instrumentarium\.instrumentarium.lock
Linux:   ~/.instrumentarium/.instrumentarium.lock
```

### Setup wizard показывается каждый раз

Удалите маркёр для сброса:
```
Windows: %LOCALAPPDATA%\Instrumentarium\.setup_done
Linux:   ~/.instrumentarium/.setup_done
```

### Console flash на Windows

Убедитесь что используется `--noconsole` и `CREATE_NO_WINDOW` для всех subprocess.

### Низкое качество видео

FFmpeg не найден. Скачайте ffmpeg и положите в `.bin/` рядом с бинарником.

---

*Последнее обновление: 2026-05-28*
