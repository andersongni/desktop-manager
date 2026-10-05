"""Detecção de modo empacotado (.exe) vs desenvolvimento (Python)."""

from __future__ import annotations

import sys
from pathlib import Path

from .paths import project_root

AGENT_EXE = "DesktopManagerAgent.exe"
ADMIN_EXE = "DesktopManagerAdmin.exe"
SETUP_EXE = "DesktopManagerSetup.exe"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def agent_cmd(root: Path | None = None, *, trigger: str = "startup", once: bool = False) -> str:
    """Linha de comando para o agente (aspas incluídas no executável)."""
    root = root or project_root()
    args = f"--trigger {trigger}"
    if once:
        args += " --once"

    exe = root / AGENT_EXE
    if exe.exists() or is_frozen():
        target = exe if exe.exists() else Path(sys.executable)
        return f'"{target}" {args}'

    py = _pythonw()
    return f'cmd /c cd /d "{root}" && "{py}" -m src.agent {args}'


def admin_launcher(root: Path | None = None) -> tuple[str, str]:
    """Retorna (target, arguments) para atalho do admin."""
    root = root or project_root()
    exe = root / ADMIN_EXE
    if exe.exists():
        return str(exe), ""
    if is_frozen():
        # Setup.exe pode abrir admin? Preferimos o Admin.exe ao lado
        return str(exe), ""
    return str(_pythonw()), "-m admin.admin_gui"


def setup_launcher(root: Path | None = None, *, uninstall: bool = False) -> tuple[str, str]:
    root = root or project_root()
    exe = root / SETUP_EXE
    flag = "--uninstall" if uninstall else "--install"
    if exe.exists():
        return str(exe), flag
    if is_frozen():
        return str(sys.executable), flag
    return str(sys.executable), f"-m src.installer {flag}"


def _pythonw() -> Path:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    if candidate.exists():
        return candidate
    return Path(sys.executable)


def distribution_files(root: Path | None = None) -> list[str]:
    """Arquivos/pastas a copiar na instalação (modo release)."""
    root = root or project_root()
    names = [
        AGENT_EXE,
        ADMIN_EXE,
        SETUP_EXE,
        "config",
        "assets",
        "README.md",
        "INSTALAR.cmd",
        "INSTALAR.vbs",
        "DESINSTALAR.cmd",
        "DESINSTALAR.vbs",
        "ADMINISTRAR.cmd",
        "TESTAR_CONFIG.cmd",
    ]
    return [n for n in names if (root / n).exists()]
