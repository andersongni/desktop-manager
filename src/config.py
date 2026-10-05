"""Carregamento e persistência da configuração."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import config_path, project_root


DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "wallpaper": {
        "enabled": True,
        "image": "assets/wallpaper/desktop.bmp",
        "style": "fill",
    },
    "organize_desktop": {
        "enabled": True,
        "rules": {
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx"],
            "Pictures": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
            "Videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv"],
            "Music": [".mp3", ".wav", ".flac", ".aac", ".ogg"],
            "Downloads": [".zip", ".rar", ".7z", ".exe", ".msi"],
        },
        "leave_shortcuts": True,
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
        "enabled": False,
        "pin": [],
        "unpin": [],
    },
    "triggers": {
        "on_startup": True,
        "on_shutdown": True,
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


def settings_for_install() -> Path:
    """Caminho da config na instalação (LOCALAPPDATA) ou do projeto em modo dev."""
    installed = project_root() / "config" / "settings.json"
    return installed
