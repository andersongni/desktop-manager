"""Organiza arquivos da área de trabalho em pastas do usuário."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import user_desktop, user_folder

logger = logging.getLogger(__name__)


def organize_desktop(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Move arquivos da Desktop conforme regras de extensão.

    Retorna lista de movimentos realizados.
    """
    desktop = user_desktop()
    rules: dict[str, list[str]] = settings.get("rules", {})
    leave_shortcuts = settings.get("leave_shortcuts", True)
    by_date = settings.get("create_subfolder_by_date", False)

    ext_map: dict[str, str] = {}
    for folder_name, extensions in rules.items():
        for ext in extensions:
            ext_map[ext.lower()] = folder_name

    moved: list[dict[str, str]] = []
    for item in desktop.iterdir():
        if item.name.startswith("."):
            continue
        if item.is_dir():
            continue
        if leave_shortcuts and item.suffix.lower() in {".lnk", ".url", ".website"}:
            continue

        folder_name = ext_map.get(item.suffix.lower())
        if not folder_name:
            continue

        dest_root = user_folder(folder_name)
        if by_date:
            dest_root = dest_root / datetime.now().strftime("%Y-%m")
            dest_root.mkdir(parents=True, exist_ok=True)

        dest = _unique_path(dest_root / item.name)
        try:
            shutil.move(str(item), str(dest))
            moved.append({"from": str(item), "to": str(dest)})
            logger.info("Movido: %s -> %s", item.name, dest)
        except OSError as exc:
            logger.warning("Não foi possível mover %s: %s", item, exc)

    logger.info("Organização concluída: %d arquivo(s)", len(moved))
    return moved


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 1
    while True:
        candidate = path.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
        n += 1
