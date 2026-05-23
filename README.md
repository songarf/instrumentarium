# 🎬 Instrumentarium

**Скачивай видео с YouTube, Twitter/X, TikTok, Instagram, Facebook, LinkedIn и 1000+ других сайтов.**

Портативное десктопное приложение. Распаковал → запустил → вставил ссылку → скачал. Без установщиков, без командной строки.

---

## ⬇️ Скачать

| Платформа | Файл | Размер |
|-----------|------|--------|
| 🪟 Windows | `VideoDownloader-windows.zip` | ~20 MB |
| 🐧 Linux | `VideoDownloader-linux.tar.gz` | ~20 MB |
| 🍎 macOS | `VideoDownloader-macos.tar.gz` | ~20 MB |

**[Скачать последнюю версию](https://github.com/songarf/instrumentarium/releases/latest)**

---

## Как использовать

### Windows
1. Скачай `VideoDownloader-windows.zip`
2. Распакуй в любую папку
3. Запусти `VideoDownloader.exe` (двойной клик)
4. Вставь ссылку → выбери Видео или Аудио → **«⬇️ Скачать»**

### Linux
```bash
tar xzf VideoDownloader-linux.tar.gz
./VideoDownloader
```

### macOS
```bash
tar xzf VideoDownloader-macos.tar.gz
./VideoDownloader
```

---

## Первый запуск

При первом запуске приложение автоматически скачает `yt-dlp` (утилита для загрузки видео). Интернет обязателен.

Видео сохраняются в папку `downloads/` рядом с приложением, разложенные по платформам:
```
downloads/
├── youtube/
├── twitter/
├── tiktok/
└── ...
```

---

## Сборка из исходников

См. [BUILD.md](BUILD.md)

## Лицензия

MIT
