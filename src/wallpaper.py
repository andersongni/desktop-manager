"""Alteração do plano de fundo da área de trabalho no Windows."""

from __future__ import annotations

import ctypes
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02

# Estilos no registro: 0=centralizar, 2=esticar, 6=ajustar, 10=preencher, 0+tile
STYLE_MAP = {
    "center": ("0", "0"),
    "stretch": ("2", "0"),
    "fit": ("6", "0"),
    "fill": ("10", "0"),
    "tile": ("0", "1"),
    "span": ("22", "0"),
}


def set_wallpaper(image_path: Path, style: str = "fill") -> bool:
    """Define a imagem como plano de fundo do Windows."""
    image_path = Path(image_path).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
    if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
        raise ValueError("Use imagem .jpg, .jpeg, .png ou .bmp")

    _apply_style(style)

    # PNG/JPG funcionam no Win10+; BMP é o formato clássico da API.
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        str(image_path),
        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
    )
    if not ok:
        raise OSError(f"Falha ao definir plano de fundo (código {ctypes.GetLastError()})")

    logger.info("Plano de fundo definido: %s (estilo=%s)", image_path, style)
    return True


def _apply_style(style: str) -> None:
    import winreg

    wallpaper_style, tile = STYLE_MAP.get(style.lower(), STYLE_MAP["fill"])
    key_path = r"Control Panel\Desktop"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style)
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile)
