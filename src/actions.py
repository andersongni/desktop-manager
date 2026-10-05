"""Orquestra todas as ações configuradas."""

from __future__ import annotations

import logging
from typing import Any

from .browser import clear_browsing_data, set_default_browser
from .organizer import organize_desktop
from .paths import resolve_asset
from .taskbar import apply_taskbar_actions
from .wallpaper import set_wallpaper

logger = logging.getLogger(__name__)


def run_all(settings: dict[str, Any], trigger: str = "manual") -> dict[str, Any]:
    """Executa o fluxo completo conforme settings.

    trigger: 'startup' | 'shutdown' | 'manual'
    """
    report: dict[str, Any] = {"trigger": trigger, "ok": True, "steps": []}

    if not settings.get("enabled", True):
        logger.info("Desktop Manager desabilitado na configuração")
        report["ok"] = False
        report["steps"].append({"step": "enabled", "status": "skipped"})
        return report

    # Wallpaper
    wp = settings.get("wallpaper", {})
    if wp.get("enabled"):
        try:
            image = resolve_asset(wp.get("image", "assets/wallpaper/desktop.jpg"))
            set_wallpaper(image, wp.get("style", "fill"))
            report["steps"].append({"step": "wallpaper", "status": "ok", "detail": str(image)})
        except Exception as exc:  # noqa: BLE001 — relatório agregado
            logger.exception("Wallpaper falhou")
            report["ok"] = False
            report["steps"].append({"step": "wallpaper", "status": "error", "detail": str(exc)})

    # Organizar Desktop
    org = settings.get("organize_desktop", {})
    if org.get("enabled"):
        try:
            moved = organize_desktop(org)
            report["steps"].append(
                {"step": "organize_desktop", "status": "ok", "detail": f"{len(moved)} arquivo(s)"}
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Organização falhou")
            report["ok"] = False
            report["steps"].append({"step": "organize_desktop", "status": "error", "detail": str(exc)})

    # Navegador padrão
    br = settings.get("browser", {})
    if br.get("set_default"):
        try:
            result = set_default_browser(br.get("default_browser", "chrome"))
            report["steps"].append({"step": "default_browser", "status": "ok", "detail": result})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Navegador padrão falhou")
            report["ok"] = False
            report["steps"].append({"step": "default_browser", "status": "error", "detail": str(exc)})

    # Limpar dados
    clear_cfg = br.get("clear_data", {})
    if clear_cfg.get("enabled"):
        try:
            cleared = clear_browsing_data(clear_cfg)
            report["steps"].append({"step": "clear_browser_data", "status": "ok", "detail": cleared})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Limpeza de navegação falhou")
            report["ok"] = False
            report["steps"].append({"step": "clear_browser_data", "status": "error", "detail": str(exc)})

    # Taskbar
    tb = settings.get("taskbar", {})
    if tb.get("enabled"):
        try:
            tb_report = apply_taskbar_actions(tb)
            report["steps"].append({"step": "taskbar", "status": "ok", "detail": tb_report})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Taskbar falhou")
            report["ok"] = False
            report["steps"].append({"step": "taskbar", "status": "error", "detail": str(exc)})

    logger.info("Fluxo '%s' finalizado (ok=%s)", trigger, report["ok"])
    return report
