"""Alteração do plano de fundo da área de trabalho no Windows."""

from __future__ import annotations

import ctypes
import logging
from pathlib import Path
from typing import Any

from .paths import project_root, resolve_asset

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

# Limiar entre 4:3 (~1.333) e 16:9 (~1.778). Abaixo → 4:3; acima → 16:9.
ASPECT_SPLIT = 1.5

DEFAULT_4X3 = "assets/wallpaper/desktop-4x3.jpg"
DEFAULT_16X9 = "assets/wallpaper/desktop-16x9.jpg"


def get_primary_screen_size() -> tuple[int, int]:
    """Retorna (largura, altura) da tela primária em pixels."""
    user32 = ctypes.windll.user32
    # Garante métricas do desktop virtual/primário atualizadas
    try:
        user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass
    width = int(user32.GetSystemMetrics(0))  # SM_CXSCREEN
    height = int(user32.GetSystemMetrics(1))  # SM_CYSCREEN
    if width <= 0 or height <= 0:
        raise OSError("Não foi possível obter a resolução da tela")
    return width, height


def classify_aspect(width: int, height: int) -> str:
    """Retorna '4x3' ou '16x9' conforme a proporção da tela."""
    ratio = width / height
    chosen = "16x9" if ratio >= ASPECT_SPLIT else "4x3"
    logger.debug("Tela %dx%d (ratio=%.3f) → %s", width, height, ratio, chosen)
    return chosen


def resolve_wallpaper_image(settings: dict[str, Any] | None = None, root: Path | None = None) -> Path:
    """Escolhe a imagem de fundo conforme aspect ratio (ou override manual)."""
    settings = settings or {}
    root = root or project_root()

    # Override explícito: se auto_aspect=false e "image" estiver definido
    auto = settings.get("auto_aspect", True)
    forced = (settings.get("image") or "").strip()
    if not auto and forced:
        path = resolve_asset(forced, root)
        if not path.exists():
            raise FileNotFoundError(f"Imagem forçada não encontrada: {path}")
        return path

    width, height = get_primary_screen_size()
    kind = classify_aspect(width, height)

    if kind == "16x9":
        candidate = settings.get("image_16x9") or DEFAULT_16X9
        fallback = settings.get("image_4x3") or DEFAULT_4X3
    else:
        candidate = settings.get("image_4x3") or DEFAULT_4X3
        fallback = settings.get("image_16x9") or DEFAULT_16X9

    # Compat: se só existir "image" antiga, usa como fallback final
    legacy = forced or DEFAULT_16X9

    for rel in (candidate, fallback, legacy):
        path = resolve_asset(rel, root)
        if path.exists():
            logger.info(
                "Wallpaper selecionado: %s (tela %dx%d → %s)",
                path.name,
                width,
                height,
                kind,
            )
            return path

    raise FileNotFoundError(
        f"Nenhuma imagem de wallpaper encontrada para tela {width}x{height} ({kind}). "
        f"Esperado: {DEFAULT_4X3} e/ou {DEFAULT_16X9}"
    )


def set_wallpaper(image_path: Path, style: str = "fill") -> bool:
    """Define a imagem como plano de fundo do Windows."""
    image_path = Path(image_path).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
    if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
        raise ValueError("Use imagem .jpg, .jpeg, .png ou .bmp")

    _apply_style(style)

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


def apply_wallpaper_from_settings(settings: dict[str, Any], root: Path | None = None) -> Path:
    """Resolve a imagem certa e aplica como plano de fundo. Retorna o path usado."""
    image = resolve_wallpaper_image(settings, root=root)
    set_wallpaper(image, settings.get("style", "fill"))
    return image


def _apply_style(style: str) -> None:
    import winreg

    wallpaper_style, tile = STYLE_MAP.get(style.lower(), STYLE_MAP["fill"])
    key_path = r"Control Panel\Desktop"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style)
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile)
