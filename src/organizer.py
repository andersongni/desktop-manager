"""Organiza a área de trabalho: atalhos permitidos + arquivos por tipo."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import user_desktop, user_folder

logger = logging.getLogger(__name__)

# Atalhos que permanecem na Desktop (demais .lnk/.url são removidos)
DEFAULT_KEEP_SHORTCUTS = ("word", "excel", "powerpoint", "chrome")

KEEP_TARGET_PATTERNS: dict[str, tuple[str, ...]] = {
    "word": ("winword.exe",),
    "excel": ("excel.exe",),
    "powerpoint": ("powerpnt.exe",),
    "chrome": ("chrome.exe", "google\\chrome"),
}

KEEP_NAME_PATTERNS: dict[str, tuple[str, ...]] = {
    "word": (r"\bword\b", r"microsoft word"),
    "excel": (r"\bexcel\b", r"microsoft excel"),
    "powerpoint": (r"powerpoint", r"power point", r"microsoft powerpoint"),
    "chrome": (r"google chrome", r"\bchrome\b"),
}


def organize_desktop(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Limpa atalhos (exceto permitidos) e move arquivos por extensão.

    Retorna lista de ações (moved / deleted / skipped).
    """
    desktop = user_desktop()
    if not desktop.exists():
        logger.warning("Área de trabalho não encontrada: %s", desktop)
        return []

    rules: dict[str, list[str]] = settings.get("rules", {})
    by_date = settings.get("create_subfolder_by_date", False)
    keep_ids = [
        str(x).lower()
        for x in settings.get("keep_shortcuts", list(DEFAULT_KEEP_SHORTCUTS))
    ]
    remove_other = settings.get("remove_other_shortcuts", True)

    ext_map: dict[str, str] = {}
    for folder_name, extensions in rules.items():
        for ext in extensions:
            ext_map[ext.lower()] = folder_name

    actions: list[dict[str, str]] = []

    for item in list(desktop.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            continue

        suffix = item.suffix.lower()

        # --- Atalhos ---
        if suffix in {".lnk", ".url", ".website"}:
            if _is_kept_shortcut(item, keep_ids):
                actions.append(
                    {
                        "action": "kept",
                        "from": str(item),
                        "to": "",
                        "detail": "atalho permitido",
                    }
                )
                logger.info("Atalho mantido: %s", item.name)
                continue
            if remove_other:
                try:
                    item.unlink(missing_ok=True)
                    actions.append(
                        {
                            "action": "deleted",
                            "from": str(item),
                            "to": "",
                            "detail": "atalho removido",
                        }
                    )
                    logger.info("Atalho removido: %s", item.name)
                except OSError as exc:
                    logger.warning("Não removeu atalho %s: %s", item, exc)
                    actions.append(
                        {
                            "action": "error",
                            "from": str(item),
                            "to": "",
                            "detail": str(exc),
                        }
                    )
            continue

        # --- Arquivos por conteúdo/extensão ---
        folder_name = ext_map.get(suffix)
        if not folder_name:
            continue

        dest_root = user_folder(folder_name)
        if by_date:
            dest_root = dest_root / datetime.now().strftime("%Y-%m")
            dest_root.mkdir(parents=True, exist_ok=True)

        dest = _unique_path(dest_root / item.name)
        try:
            shutil.move(str(item), str(dest))
            actions.append({"action": "moved", "from": str(item), "to": str(dest), "detail": folder_name})
            logger.info("Movido: %s -> %s", item.name, dest)
        except OSError as exc:
            logger.warning("Não foi possível mover %s: %s", item, exc)
            actions.append(
                {"action": "error", "from": str(item), "to": "", "detail": str(exc)}
            )

    moved_n = sum(1 for a in actions if a.get("action") == "moved")
    deleted_n = sum(1 for a in actions if a.get("action") == "deleted")
    kept_n = sum(1 for a in actions if a.get("action") == "kept")
    logger.info(
        "Organização concluída: %d movido(s), %d atalho(s) removido(s), %d atalho(s) mantido(s)",
        moved_n,
        deleted_n,
        kept_n,
    )
    return actions


def _is_kept_shortcut(path: Path, keep_ids: list[str]) -> bool:
    name = path.stem.lower()
    target = (_shortcut_target(path) or "").lower().replace("/", "\\")

    for app_id in keep_ids:
        for pat in KEEP_NAME_PATTERNS.get(app_id, ()):
            if re.search(pat, name, re.IGNORECASE):
                return True
        for token in KEEP_TARGET_PATTERNS.get(app_id, ()):
            if token.lower() in target:
                return True
    return False


def _shortcut_target(path: Path) -> str | None:
    """Resolve o destino de um .lnk (ou .url)."""
    if path.suffix.lower() == ".url":
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.lower().startswith("url="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            return None
        return None

    if path.suffix.lower() != ".lnk":
        return None

    target_ps = str(path).replace("'", "''")
    ps = f"""
$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut('{target_ps}')
Write-Output $s.TargetPath
"""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).strip()
        return out or None
    except (subprocess.SubprocessError, OSError):
        return None


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
