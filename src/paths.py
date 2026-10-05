"""Caminhos do projeto e pastas do usuário."""

from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def project_root() -> Path:
    """Raiz do projeto (pasta que contém config/, src/, assets/)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def install_dir() -> Path:
    """Diretório de instalação padrão do usuário."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "DesktopManager"


def config_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "config" / "settings.json"


def log_dir(root: Path | None = None) -> Path:
    d = (root or project_root()) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


@lru_cache(maxsize=16)
def _known_folder(name: str) -> Path | None:
    """Resolve pastas especiais via PowerShell ([Environment]::GetFolderPath)."""
    map_names = {
        "Desktop": "Desktop",
        "Documents": "MyDocuments",
        "Pictures": "MyPictures",
        "Videos": "MyVideos",
        "Music": "MyMusic",
    }
    folder = map_names.get(name)
    if not folder:
        return None
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"[Environment]::GetFolderPath('{folder}')",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).strip()
        if out:
            return Path(out)
    except (subprocess.CalledProcessError, OSError):
        pass
    return None


def user_desktop() -> Path:
    resolved = _known_folder("Desktop")
    if resolved and resolved.exists():
        return resolved
    for candidate in (
        Path.home() / "Desktop",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "OneDrive" / "Área de Trabalho",
    ):
        if candidate.exists():
            return candidate
    return Path.home() / "Desktop"


def user_folder(name: str) -> Path:
    """Resolve pastas conhecidas do perfil (Documents, Pictures, etc.)."""
    aliases = {
        "Documentos": "Documents",
        "Imagens": "Pictures",
        "Vídeos": "Videos",
        "Videos": "Videos",
        "Músicas": "Music",
        "Musicas": "Music",
        "Downloads": "Downloads",
        "Área de Trabalho": "Desktop",
        "Area de Trabalho": "Desktop",
        "Documents": "Documents",
        "Pictures": "Pictures",
        "Music": "Music",
        "Desktop": "Desktop",
    }
    key = aliases.get(name, name)

    if key == "Desktop":
        path = user_desktop()
    elif key == "Downloads":
        path = Path.home() / "Downloads"
    else:
        resolved = _known_folder(key)
        fallbacks = {
            "Documents": Path.home() / "Documents",
            "Pictures": Path.home() / "Pictures",
            "Videos": Path.home() / "Videos",
            "Music": Path.home() / "Music",
        }
        path = resolved or fallbacks.get(key) or (Path.home() / name)

    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_asset(relative: str, root: Path | None = None) -> Path:
    p = Path(relative)
    if p.is_absolute():
        return p
    return (root or project_root()) / p
