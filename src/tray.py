"""Ícone na área de notificação (bandeja) com menu de contexto."""

from __future__ import annotations

import ctypes
import logging
import subprocess
import sys
import threading
from ctypes import wintypes
from typing import Callable

from .app_icon import app_icon_ico
from .paths import project_root
from .runtime import app_executable

logger = logging.getLogger(__name__)

WM_TRAYICON = 0x0400 + 21
WM_COMMAND = 0x0111
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_CHECKED = 0x00000008
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

ID_ADMIN = 1001
ID_RUN_NOW = 1002
ID_UPDATE = 1003
ID_AUTOSTART = 1004
ID_WIZARD = 1005
ID_EXIT = 1006


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class TrayController:
    """Controla o ícone da bandeja ligado à janela oculta do agente."""

    def __init__(
        self,
        hwnd: int,
        *,
        on_exit: Callable[[], None] | None = None,
        get_autostart: Callable[[], bool] | None = None,
        set_autostart: Callable[[bool], None] | None = None,
        on_run_now: Callable[[], None] | None = None,
        on_update: Callable[[], None] | None = None,
    ) -> None:
        self.hwnd = int(hwnd)
        self.on_exit = on_exit
        self.get_autostart = get_autostart or (lambda: False)
        self.set_autostart = set_autostart
        self.on_run_now = on_run_now
        self.on_update = on_update
        self._uid = 1
        self._hicon = None
        self._added = False
        self.shell32 = ctypes.windll.shell32
        self.user32 = ctypes.windll.user32

    def add(self, tip: str = "Desktop Manager") -> bool:
        hicon = self._load_icon()
        if not hicon:
            logger.warning("Ícone da bandeja indisponível")
            return False
        self._hicon = hicon
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = self._uid
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = hicon
        nid.szTip = tip[:127]
        ok = bool(self.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
        self._added = ok
        if ok:
            logger.info("Ícone da bandeja ativo")
        else:
            logger.warning("Shell_NotifyIcon ADD falhou")
        return ok

    def notify(self, title: str, message: str) -> None:
        if not self._added:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = self._uid
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = title[:63]
        nid.szInfo = message[:255]
        nid.dwInfoFlags = NIIF_INFO
        self.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def remove(self) -> None:
        if not self._added:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = self._uid
        self.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        self._added = False
        if self._hicon:
            self.user32.DestroyIcon(self._hicon)
            self._hicon = None

    def handle_message(self, msg: int, wparam: int, lparam: int) -> bool:
        if msg == WM_TRAYICON and wparam == self._uid:
            event = lparam & 0xFFFF
            if event == WM_LBUTTONDBLCLK:
                self._open_admin()
                return True
            if event == WM_RBUTTONUP:
                self._show_menu()
                return True
        if msg == WM_COMMAND:
            self._dispatch_command(wparam & 0xFFFF)
            return True
        return False

    def _load_icon(self):
        path = app_icon_ico()
        if path is None:
            return self.user32.LoadIconW(None, 32512)  # IDI_APPLICATION
        handle = self.user32.LoadImageW(
            None,
            str(path),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE,
        )
        return handle or self.user32.LoadIconW(None, 32512)

    def _show_menu(self) -> None:
        menu = self.user32.CreatePopupMenu()
        if not menu:
            return
        autostart = False
        try:
            autostart = bool(self.get_autostart())
        except Exception:  # noqa: BLE001
            logger.debug("Falha ao ler autostart", exc_info=True)

        self.user32.AppendMenuW(menu, MF_STRING, ID_ADMIN, "Abrir configurações")
        self.user32.AppendMenuW(menu, MF_STRING, ID_RUN_NOW, "Executar ações agora")
        self.user32.AppendMenuW(menu, MF_STRING, ID_UPDATE, "Verificar atualizações")
        self.user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        flags = MF_STRING | (MF_CHECKED if autostart else 0)
        self.user32.AppendMenuW(menu, flags, ID_AUTOSTART, "Inicializar com o Windows")
        self.user32.AppendMenuW(menu, MF_STRING, ID_WIZARD, "Assistente (instalar/atualizar)…")
        self.user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        self.user32.AppendMenuW(menu, MF_STRING, ID_EXIT, "Encerrar Desktop Manager")

        pt = POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        self.user32.SetForegroundWindow(self.hwnd)
        cmd = self.user32.TrackPopupMenu(
            menu,
            TPM_RIGHTBUTTON | TPM_RETURNCMD,
            pt.x,
            pt.y,
            0,
            self.hwnd,
            None,
        )
        self.user32.DestroyMenu(menu)
        self.user32.PostMessageW(self.hwnd, 0, 0, 0)  # evita menu fantasma
        if cmd:
            self._dispatch_command(int(cmd))

    def _dispatch_command(self, cmd: int) -> None:
        if cmd == ID_ADMIN:
            self._open_admin()
        elif cmd == ID_RUN_NOW:
            if self.on_run_now:
                threading.Thread(target=self.on_run_now, daemon=True).start()
            else:
                self._spawn("--trigger", "manual", "--once")
        elif cmd == ID_UPDATE:
            if self.on_update:
                threading.Thread(target=self.on_update, daemon=True).start()
            else:
                self._spawn("--admin")
        elif cmd == ID_AUTOSTART:
            if self.set_autostart:
                try:
                    current = bool(self.get_autostart())
                    self.set_autostart(not current)
                    state = "ativada" if not current else "desativada"
                    self.notify("Desktop Manager", f"Inicialização com o Windows {state}.")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Falha ao alternar autostart")
                    self.notify("Desktop Manager", f"Não foi possível alterar: {exc}")
        elif cmd == ID_WIZARD:
            self._spawn("--wizard")
        elif cmd == ID_EXIT:
            self.remove()
            if self.on_exit:
                self.on_exit()

    def _open_admin(self) -> None:
        self._spawn("--admin")

    def _spawn(self, *args: str) -> None:
        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen(
                    [app_executable(), *args],
                    cwd=str(project_root()),
                    close_fds=True,
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(project_root() / "entry_app.py"), *args],
                    cwd=str(project_root()),
                    close_fds=True,
                )
        except OSError as exc:
            logger.warning("Falha ao abrir %s: %s", args, exc)
