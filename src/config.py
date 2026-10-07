"""Carregamento e persistência da configuração."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import config_path


DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "wallpaper": {
        "enabled": True,
        "auto_aspect": True,
        "image_4x3": "assets/wallpaper/desktop-4x3.jpg",
        "image_16x9": "assets/wallpaper/desktop-16x9.jpg",
        "image": "",
        "style": "fill",
    },
    "organize_desktop": {
        "enabled": True,
        "rules": {
            "Documents": [
                ".pdf",
                ".doc",
                ".docx",
                ".txt",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
                ".odt",
                ".rtf",
                ".csv",
            ],
            "Pictures": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".heic"],
            "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".webm"],
            "Music": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"],
            "Downloads": [".zip", ".rar", ".7z", ".exe", ".msi", ".iso"],
        },
        "keep_shortcuts": ["word", "excel", "powerpoint", "chrome"],
        "remove_other_shortcuts": True,
        "create_subfolder_by_date": False,
    },
    "browser": {
        "set_default": False,
        "default_browser": "chrome",
        "clear_data": {
            "enabled": True,
            "browsers": ["chrome", "edge", "firefox"],
            "clear_cache": True,
            "clear_cookies": False,
            "clear_history": False,
        },
    },
    "taskbar": {
        "enabled": True,
        "replace": True,
        "pins": ["explorer", "word", "excel", "powerpoint", "chrome"],
    },
    "triggers": {
        "on_startup": True,
        "on_shutdown": True,
    },
    "updates": {
        "enabled": True,
        "auto_apply": True,
        "check_interval_hours": 6,
        "github_repo": "andersongni/desktop-manager",
    },
    "logging": {
        "level": "INFO",
        "keep_days": 30,
    },
}


def load_settings(path: Path | None = None) -> dict[str, Any]:
    cfg = path or config_path()
    if not cfg.exists():
        settings = deepcopy(DEFAULT_SETTINGS)
        save_settings(settings, cfg)
        return settings
    with cfg.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return _merge(deepcopy(DEFAULT_SETTINGS), data)


def save_settings(settings: dict[str, Any], path: Path | None = None) -> Path:
    cfg = path or config_path()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    with cfg.open("w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return cfg


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge(base[key], value)
        else:
            base[key] = value
    return base
