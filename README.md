# 🎬 Instrumentarium

**Скачивай видео с YouTube, Twitter/X, TikTok, Instagram, Facebook, LinkedIn и 1000+ других сайтов.**

Портативное десктопное приложение. Распаковал → запустил → вставил ссылку → скачал. Без установщиков, без командной строки.

---

## ⬇️ Скачать

| Платформа | Файл | Размер |
|-----------|------|--------|
| 🪟 Windows | `Instrumentarium-windows.zip` | ~20 MB |
| 🐧 Linux | `Instrumentarium-linux.tar.gz` | ~20 MB |
| 🍎 macOS | `Instrumentarium-macos.tar.gz` | ~20 MB |

**[Скачать последнюю версию](https://github.com/songarf/instrumentarium/releases/latest)**

---

## Как использовать

### Windows
1. Скачай `Instrumentarium-windows.zip`
2. Распакуй в любую папку
3. Запусти `Instrumentarium.exe` (двойной клик)
4. Вставь ссылку → выбери Видео или Аудио → **«⬇️ Скачать»**

### Linux
```bash
tar xzf Instrumentarium-linux.tar.gz
./Instrumentarium
```

### macOS
```bash
tar xzf Instrumentarium-macos.tar.gz
./Instrumentarium
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
