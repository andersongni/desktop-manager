"""Agente em segundo plano — bandeja, logon e desligamento."""

from __future__ import annotations

import argparse
import atexit
import ctypes
import logging
import sys
import time
from typing import Any

from .actions import run_all
from .app_icon import app_icon_ico
from .config import load_settings
from .installer import is_autostart_enabled, set_autostart
from .logging_setup import setup_logging
from .tray import TrayController

logger = logging.getLogger(__name__)

CTRL_CLOSE_EVENT = 2
CTRL_LOGOFF_EVENT = 5
CTRL_SHUTDOWN_EVENT = 6

WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010

_shutdown_done = False
_settings: dict[str, Any] = {}
_wnd_proc_ref = None  # evita GC do callback
_tray: TrayController | None = None
_exit_requested = False


def _run_shutdown() -> None:
    global _shutdown_done
    if _shutdown_done:
        return
    _shutdown_done = True
    if not _settings.get("triggers", {}).get("on_shutdown", True):
        logger.info("Trigger on_shutdown desabilitado")
        return
    logger.info("Desligamento detectado — executando ações")
    try:
        run_all(_settings, trigger="shutdown")
    except Exception:  # noqa: BLE001
        logger.exception("Erro no fluxo de desligamento")


def _ctrl_handler(ctrl_type: int) -> bool:
    if ctrl_type in (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
        _run_shutdown()
        return True
    return False


def _install_ctrl_handler() -> None:
    handler = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(_ctrl_handler)
    _install_ctrl_handler._handler = handler  # type: ignore[attr-defined]
    try:
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True)
    except Exception:  # noqa: BLE001
        logger.debug("SetConsoleCtrlHandler indisponível (pythonw)")


def _request_exit() -> None:
    global _exit_requested
    _exit_requested = True
    try:
        ctypes.windll.user32.PostQuitMessage(0)
    except Exception:  # noqa: BLE001
        pass


def _run_now() -> None:
    try:
        settings = load_settings()
        report = run_all(settings, trigger="manual")
        ok = report.get("ok", False)
        if _tray:
            _tray.notify(
                "Desktop Manager",
                "Ações concluídas." if ok else "Ações concluídas com avisos/erros.",
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Execução manual falhou")
        if _tray:
            _tray.notify("Desktop Manager", f"Falha: {exc}")


def _check_updates() -> None:
    try:
        from .updater import maybe_auto_update
        from .version import current_version

        settings = load_settings()
        result = maybe_auto_update(settings)
        msg = {
            "up_to_date": f"Já está na versão mais recente (v{current_version()}).",
            "available": f"Nova versão disponível: v{result.remote_version}.",
            "downloaded": f"Atualização baixada (v{result.remote_version}).",
            "applied": f"Atualizado para v{result.remote_version}.",
            "scheduled": "Atualização agendada — o app será reiniciado.",
            "skipped": result.detail or "Verificação ignorada.",
            "error": result.detail or "Falha ao verificar atualizações.",
        }.get(result.status, result.detail or result.status)
        if _tray:
            _tray.notify("Desktop Manager", msg)
        if result.status == "scheduled":
            _request_exit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Update via bandeja falhou")
        if _tray:
            _tray.notify("Desktop Manager", f"Falha na atualização: {exc}")


def _message_loop() -> None:
    """Janela oculta: WM_ENDSESSION + ícone da bandeja."""
    global _wnd_proc_ref, _tray

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    LRESULT = ctypes.c_ssize_t
    WPARAM = ctypes.c_size_t
    LPARAM = ctypes.c_ssize_t
    HWND = ctypes.c_void_p

    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, ctypes.c_uint, WPARAM, LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", ctypes.c_uint),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", ctypes.c_void_p),
            ("hIcon", ctypes.c_void_p),
            ("hCursor", ctypes.c_void_p),
            ("hbrBackground", ctypes.c_void_p),
            ("lpszMenuName", ctypes.c_wchar_p),
            ("lpszClassName", ctypes.c_wchar_p),
        ]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", HWND),
            ("message", ctypes.c_uint),
            ("wParam", WPARAM),
            ("lParam", LPARAM),
            ("time", ctypes.c_uint),
            ("pt_x", ctypes.c_long),
            ("pt_y", ctypes.c_long),
        ]

    @WNDPROC
    def wnd_proc(hwnd, msg, wparam, lparam):
        if _tray and _tray.handle_message(int(msg), int(wparam), int(lparam)):
            return 0
        if msg in (WM_QUERYENDSESSION, WM_ENDSESSION):
            _run_shutdown()
            return 1
        if msg in (WM_DESTROY, WM_CLOSE):
            if _tray:
                _tray.remove()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _wnd_proc_ref = wnd_proc

    class_name = "DesktopManagerAgentWindow"
    h_instance = kernel32.GetModuleHandleW(None)

    hicon = None
    ico = app_icon_ico()
    if ico is not None:
        hicon = user32.LoadImageW(None, str(ico), 1, 0, 0, 0x0010)

    wc = WNDCLASSW()
    wc.style = 0
    wc.lpfnWndProc = wnd_proc
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = h_instance
    wc.hIcon = hicon
    wc.hCursor = None
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = class_name

    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom and ctypes.GetLastError() not in (0, 1410):
        logger.warning("RegisterClassW falhou (%s) — modo sleep", ctypes.GetLastError())
        while not _exit_requested:
            time.sleep(3600)
        return

    hwnd = user32.CreateWindowExW(
        0,
        class_name,
        "Desktop Manager",
        0,
        0,
        0,
        0,
        0,
        None,
        None,
        h_instance,
        None,
    )
    if not hwnd:
        logger.warning("CreateWindowExW falhou — modo sleep")
        while not _exit_requested:
            time.sleep(3600)
        return

    hwnd_int = hwnd if isinstance(hwnd, int) else int(ctypes.cast(hwnd, ctypes.c_void_p).value or 0)
    _tray = TrayController(
        hwnd_int,
        on_exit=_request_exit,
        get_autostart=is_autostart_enabled,
        set_autostart=lambda enabled: set_autostart(enabled),
        on_run_now=_run_now,
        on_update=_check_updates,
    )
    _tray.add("Desktop Manager — em execução")

    logger.info("Agente residente com bandeja (hwnd=%s)", hwnd_int)
    msg = MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    if _tray:
        _tray.remove()
        _tray = None


def run_agent(
    once: bool = False,
    trigger: str = "startup",
    *,
    no_actions: bool = False,
) -> int:
    global _settings
    _settings = load_settings()
    log_cfg = _settings.get("logging", {})
    setup_logging(log_cfg.get("level", "INFO"), log_cfg.get("keep_days", 30))

    logger.info(
        "Desktop Manager Agent iniciando (once=%s, trigger=%s, no_actions=%s)",
        once,
        trigger,
        no_actions,
    )

    # Auto-update no logon (antes das arrumações). Se agendado, encerra para trocar os EXEs.
    if trigger == "startup" and not no_actions:
        try:
            from .updater import maybe_auto_update
            from .version import current_version

            result = maybe_auto_update(_settings)
            logger.info(
                "Update check: %s (local=%s remote=%s) %s",
                result.status,
                result.local_version or current_version(),
                result.remote_version or "-",
                result.detail,
            )
            if result.status == "scheduled":
                logger.info("Saindo para aplicar atualização…")
                return 0
        except Exception:  # noqa: BLE001
            logger.exception("Falha no verificador de atualizações")

    if not no_actions:
        if trigger == "startup" and _settings.get("triggers", {}).get("on_startup", True):
            run_all(_settings, trigger="startup")
        elif trigger in ("shutdown", "manual"):
            run_all(_settings, trigger=trigger)

    if once:
        return 0

    atexit.register(_run_shutdown)
    _install_ctrl_handler()

    try:
        _message_loop()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
        _run_shutdown()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Desktop Manager Agent")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa as ações uma vez e encerra (não fica residente)",
    )
    parser.add_argument(
        "--trigger",
        choices=["startup", "shutdown", "manual"],
        default="startup",
        help="Qual fluxo executar",
    )
    parser.add_argument(
        "--no-actions",
        action="store_true",
        help="Só fica residente (pós-atualização; não reexecuta arrumações)",
    )
    args = parser.parse_args(argv)
    return run_agent(once=args.once, trigger=args.trigger, no_actions=args.no_actions)


if __name__ == "__main__":
    sys.exit(main())
