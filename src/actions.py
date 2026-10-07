"""Orquestra todas as ações configuradas."""

from __future__ import annotations

import logging
from typing import Any

from .browser import clear_browsing_data, ensure_browser_installed, set_default_browser
from .organizer import organize_desktop
from .taskbar import apply_taskbar_actions
from .wallpaper import apply_wallpaper_from_settings, get_primary_screen_size

logger = logging.getLogger(__name__)

# Arrumações do ambiente: só no início/fim da sessão — nunca durante o uso.
SESSION_EDGE_TRIGGERS = frozenset({"startup", "shutdown"})
SKIP_DETAIL = "somente no início ou desligamento da sessão"


def run_all(settings: dict[str, Any], trigger: str = "manual") -> dict[str, Any]:
    """Executa o fluxo completo conforme settings.

    trigger: 'startup' | 'shutdown' | 'manual'

    Wallpaper, organização da Desktop, limpeza de navegador, navegador padrão
    e barra de tarefas só rodam em startup/shutdown.
    """
    report: dict[str, Any] = {"trigger": trigger, "ok": True, "steps": []}
    session_edge = trigger in SESSION_EDGE_TRIGGERS

    if not settings.get("enabled", True):
        logger.info("Desktop Manager desabilitado na configuração")
        report["ok"] = False
        report["steps"].append({"step": "enabled", "status": "skipped"})
        return report

    if not session_edge:
        logger.info(
            "Trigger '%s': arrumações de ambiente ignoradas (só startup/shutdown)",
            trigger,
        )

    # Wallpaper
    wp = settings.get("wallpaper", {})
    if wp.get("enabled"):
        if not session_edge:
            report["steps"].append(
                {"step": "wallpaper", "status": "skipped", "detail": SKIP_DETAIL}
            )
        else:
            try:
                image = apply_wallpaper_from_settings(wp)
                try:
                    w, h = get_primary_screen_size()
                    screen = f"{w}x{h}"
                except OSError:
                    screen = "?"
                report["steps"].append(
                    {
                        "step": "wallpaper",
                        "status": "ok",
                        "detail": {"image": str(image), "screen": screen},
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Wallpaper falhou")
                report["ok"] = False
                report["steps"].append(
                    {"step": "wallpaper", "status": "error", "detail": str(exc)}
                )

    # Organizar Desktop
    org = settings.get("organize_desktop", {})
    if org.get("enabled"):
        if not session_edge:
            report["steps"].append(
                {"step": "organize_desktop", "status": "skipped", "detail": SKIP_DETAIL}
            )
        else:
            try:
                org_report = organize_desktop(org)
                summary = {
                    "moved": sum(1 for a in org_report if a.get("action") == "moved"),
                    "shortcuts_removed": sum(
                        1 for a in org_report if a.get("action") == "deleted"
                    ),
                    "shortcuts_kept": sum(1 for a in org_report if a.get("action") == "kept"),
                    "trigger": trigger,
                }
                report["steps"].append(
                    {"step": "organize_desktop", "status": "ok", "detail": summary}
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Organização falhou")
                report["ok"] = False
                report["steps"].append(
                    {"step": "organize_desktop", "status": "error", "detail": str(exc)}
                )

    # Navegador (instalar se faltar + definir como padrão)
    br = settings.get("browser", {})
    default_browser = str(br.get("default_browser", "chrome")).lower()
    ensure_installed = bool(br.get("ensure_installed", True))
    set_default = bool(br.get("set_default", True))

    if ensure_installed and not set_default:
        if not session_edge:
            report["steps"].append(
                {"step": "ensure_browser", "status": "skipped", "detail": SKIP_DETAIL}
            )
        else:
            try:
                result = ensure_browser_installed(default_browser)
                report["steps"].append(
                    {"step": "ensure_browser", "status": "ok", "detail": result}
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Garantia de instalação do navegador falhou")
                report["ok"] = False
                report["steps"].append(
                    {"step": "ensure_browser", "status": "error", "detail": str(exc)}
                )

    if set_default:
        if not session_edge:
            report["steps"].append(
                {"step": "default_browser", "status": "skipped", "detail": SKIP_DETAIL}
            )
        else:
            try:
                result = set_default_browser(
                    default_browser,
                    install_if_missing=ensure_installed,
                )
                report["steps"].append(
                    {"step": "default_browser", "status": "ok", "detail": result}
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Navegador padrão falhou")
                report["ok"] = False
                report["steps"].append(
                    {"step": "default_browser", "status": "error", "detail": str(exc)}
                )

    clear_cfg = br.get("clear_data", {})
    if clear_cfg.get("enabled"):
        if not session_edge:
            report["steps"].append(
                {"step": "clear_browser_data", "status": "skipped", "detail": SKIP_DETAIL}
            )
        else:
            try:
                cleared = clear_browsing_data(clear_cfg)
                report["steps"].append(
                    {"step": "clear_browser_data", "status": "ok", "detail": cleared}
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Limpeza de navegação falhou")
                report["ok"] = False
                report["steps"].append(
                    {"step": "clear_browser_data", "status": "error", "detail": str(exc)}
                )

    # Taskbar
    tb = settings.get("taskbar", {})
    if tb.get("enabled"):
        if not session_edge:
            report["steps"].append(
                {"step": "taskbar", "status": "skipped", "detail": SKIP_DETAIL}
            )
        else:
            try:
                tb_report = apply_taskbar_actions(tb)
                report["steps"].append(
                    {"step": "taskbar", "status": "ok", "detail": tb_report}
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Taskbar falhou")
                report["ok"] = False
                report["steps"].append(
                    {"step": "taskbar", "status": "error", "detail": str(exc)}
                )

    logger.info("Fluxo '%s' finalizado (ok=%s)", trigger, report["ok"])
    return report
