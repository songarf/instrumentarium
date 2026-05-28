"""Tests for server.py functions (isolated, no network, no yt-dlp)."""
import os, sys, tempfile, json
from unittest.mock import patch, MagicMock

# Add parent to path so we can import server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── detect_platform ──────────────────────────────────────────────────

def test_detect_platform_youtube():
    from server import detect_platform
    assert detect_platform("https://youtube.com/watch?v=xyz") == "youtube"
    assert detect_platform("https://youtu.be/xyz") == "youtube"
    assert detect_platform("https://www.youtube.com/shorts/xyz") == "youtube"


def test_detect_platform_twitter():
    from server import detect_platform
    assert detect_platform("https://twitter.com/user/status/123") == "twitter"
    assert detect_platform("https://x.com/user/status/123") == "twitter"


def test_detect_platform_tiktok():
    from server import detect_platform
    assert detect_platform("https://tiktok.com/@user/video/123") == "tiktok"


def test_detect_platform_instagram():
    from server import detect_platform
    assert detect_platform("https://instagram.com/p/xyz") == "instagram"
    assert detect_platform("https://www.instagram.com/reel/xyz") == "instagram"


def test_detect_platform_facebook():
    from server import detect_platform
    assert detect_platform("https://facebook.com/watch?v=xyz") == "facebook"
    assert detect_platform("https://fb.watch/xyz") == "facebook"
    assert detect_platform("https://fb.com/xyz") == "facebook"


def test_detect_platform_linkedin():
    from server import detect_platform
    assert detect_platform("https://linkedin.com/posts/xyz") == "linkedin"


def test_detect_platform_other():
    from server import detect_platform
    assert detect_platform("https://vimeo.com/123") == "other"
    assert detect_platform("https://example.com/video") == "other"


def test_detect_platform_case_insensitive():
    from server import detect_platform
    assert detect_platform("https://YouTube.com/watch?v=xyz") == "youtube"


def test_detect_platform_empty():
    from server import detect_platform
    assert detect_platform("") == "other"


# ── _human (file size formatting) ────────────────────────────────────

def test_human_bytes():
    from server import _human
    assert _human(0) == "0.0 B"
    assert _human(500) == "500.0 B"
    assert _human(1023) == "1023.0 B"


def test_human_kb():
    from server import _human
    assert _human(1024) == "1.0 KB"
    assert _human(1536) == "1.5 KB"
    assert _human(1024 * 100) == "100.0 KB"


def test_human_mb():
    from server import _human
    assert _human(1024 * 1024) == "1.0 MB"
    assert _human(1024 * 1024 * 15) == "15.0 MB"


def test_human_gb():
    from server import _human
    assert _human(1024 ** 3) == "1.0 GB"
    assert _human(1024 ** 3 * 2) == "2.0 GB"


def test_human_tb():
    from server import _human
    assert _human(1024 ** 4) == "1.0 TB"


# ── find_system_python ───────────────────────────────────────────────

@patch("server.shutil.which")
@patch("server.subprocess.check_output")
def test_find_system_python_found(mock_check, mock_which):
    from server import find_system_python
    mock_which.return_value = "/usr/bin/python3"
    mock_check.return_value = "Python 3.12.0"
    path, ver = find_system_python()
    assert path == "/usr/bin/python3"
    assert "Python 3.12.0" in ver


@patch("server.shutil.which")
def test_find_system_python_not_found(mock_which):
    from server import find_system_python
    mock_which.return_value = None
    path, ver = find_system_python()
    assert path is None
    assert ver is None


@patch("server.shutil.which")
@patch("server.subprocess.check_output")
def test_find_system_python_too_old(mock_check, mock_which):
    from server import find_system_python
    mock_which.return_value = "/usr/bin/python3"
    mock_check.return_value = "Python 2.7.18"
    path, ver = find_system_python()
    assert path is None
    assert ver is None


# ── get_python_install_url ───────────────────────────────────────────

@patch("server.platform.system")
@patch("server.platform.machine")
def test_get_python_install_url_windows_64(mock_machine, mock_system):
    from server import get_python_install_url
    mock_system.return_value = "Windows"
    mock_machine.return_value = "AMD64"
    url = get_python_install_url()
    assert "python-3.12.9-amd64.exe" in url


@patch("server.platform.system")
def test_get_python_install_url_linux(mock_system):
    from server import get_python_install_url
    mock_system.return_value = "Linux"
    url = get_python_install_url()
    assert url is None


# ── check_ytdlp ──────────────────────────────────────────────────────

@patch("server.os.path.isfile")
@patch("server.subprocess.check_output")
def test_check_ytdlp_found_in_bin(mock_check, mock_isfile):
    from server import check_ytdlp
    mock_isfile.return_value = True
    mock_check.return_value = "2026.01.01"
    ok, ver = check_ytdlp()
    assert ok is True
    assert ver == "2026.01.01"


@patch("server.os.path.isfile")
def test_check_ytdlp_not_found(mock_isfile):
    from server import check_ytdlp
    mock_isfile.return_value = False
    ok, ver = check_ytdlp()
    assert ok is False
    assert ver is None


# ── HTTP handler: /status endpoint ───────────────────────────────────

def test_status_endpoint_json():
    from server import setup_state
    import json
    # Simulate a state
    setup_state["phase"] = "done"
    setup_state["progress"] = 100
    as_json = json.dumps({
        "phase": setup_state["phase"],
        "progress": setup_state["progress"],
        "messages": setup_state["messages"],
        "python_ok": setup_state["python_ok"],
        "ytdlp_ok": setup_state["ytdlp_ok"],
        "server_started": setup_state["server_started"],
        "error": setup_state["error"],
        "setup_done": setup_state["setup_done"],
    })
    data = json.loads(as_json)
    assert data["phase"] == "done"
    assert data["progress"] == 100
    assert "phase" in data
    assert "messages" in data


# ── NEW: _map_ytdlp_error tests ──────────────────────────────────────

def test_map_ytdlp_error():
    from server import _map_ytdlp_error
    # Valid error mappings
    assert _map_ytdlp_error("Unsupported URL") == "Неправильная ссылка или сайт не поддерживается"
    assert _map_ytdlp_error("Video unavailable") == "Видео недоступно или удалено"
    assert _map_ytdlp_error("Private video") == "Видео приватное — нужны cookies для доступа"
    assert _map_ytdlp_error("Login required") == "Требуется вход в аккаунт — загрузите cookies"
    assert _map_ytdlp_error("403 Forbidden") == "Доступ заблокирован — попробуйте позже или используйте cookies"
    assert _map_ytdlp_error("404 Not Found") == "Страница не найдена (404)"
    assert _map_ytdlp_error("429 Rate limit") == "Слишком много запросов — подождите и попробуйте снова"
    assert _map_ytdlp_error("Network error") == "Ошибка сети — проверьте подключение к интернету"
    assert _map_ytdlp_error("Geo-blocked") == "Доступ заблокирован — попробуйте позже или используйте cookies"
    assert _map_ytdlp_error("Removed/Deleted") == "Видео было удалено"
    assert _map_ytdlp_error("Copyright/DMCA") == "Видео заблокировано по запросу правообладателя"
    assert _map_ytdlp_error("Age restricted") == "Видео с возрастным ограничением — нужны cookies"
    # Fallback
    assert _map_ytdlp_error("Other") == "Не удалось обработать ссылку — проверьте правильность или используйте cookies"
    # Edge cases
    assert _map_ytdlp_error("") == "Не удалось обработать ссылку — проверьте правильность или используйте cookies"
    assert _map_ytdlp_error(None) == "Не удалось обработать ссылку — проверьте правильность или используйте cookies"


# ── Run all ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))