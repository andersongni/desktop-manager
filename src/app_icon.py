"""Resolução do ícone do aplicativo (EXE, janelas e bandeja)."""

from __future__ import annotations

import sys
from pathlib import Path

from .paths import project_root


def bundle_root() -> Path:
    """Pasta com recursos embutidos (PyInstaller) ou raiz do projeto."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return project_root()


def app_icon_ico() -> Path | None:
    candidates = [
        project_root() / "assets" / "icon" / "app.ico",
        bundle_root() / "assets" / "icon" / "app.ico",
        Path(sys.executable).with_suffix(".ico") if getattr(sys, "frozen", False) else None,
    ]
    for path in candidates:
        if path is not None and path.exists():
            return path
    return None


def app_icon_png() -> Path | None:
    candidates = [
        project_root() / "assets" / "icon" / "app.png",
        bundle_root() / "assets" / "icon" / "app.png",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def apply_window_icon(root) -> None:
    """Aplica o ícone a uma janela Tk (e filhas)."""
    ico = app_icon_ico()
    png = app_icon_png()
    try:
        if ico is not None and sys.platform == "win32":
            root.iconbitmap(default=str(ico))
            root.iconbitmap(str(ico))
    except Exception:  # noqa: BLE001
        pass
    if png is None:
        return
    try:
        from tkinter import PhotoImage

        img = PhotoImage(file=str(png))
        root.iconphoto(True, img)
        root._app_icon_photo = img  # evita GC
    except Exception:  # noqa: BLE001
        pass
