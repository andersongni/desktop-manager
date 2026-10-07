"""Detecção de modo empacotado (.exe) vs desenvolvimento (Python)."""

from __future__ import annotations

import sys
from pathlib import Path

from .paths import install_dir, project_root

# Executável único standalone (instalador / agente / admin)
APP_EXE = "DesktopManager.exe"
# Nomes legados mantidos para pacotes antigos / compatibilidade
AGENT_EXE = "DesktopManagerAgent.exe"
ADMIN_EXE = "DesktopManagerAdmin.exe"
SETUP_EXE = "DesktopManagerSetup.exe"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_executable(root: Path | None = None) -> str:
    """Caminho do executável principal (instalado ou atual)."""
    root = root or project_root()
    for name in (APP_EXE, AGENT_EXE, SETUP_EXE):
        candidate = root / name
        if candidate.exists():
            return str(candidate)
    installed = install_dir() / APP_EXE
    if installed.exists():
        return str(installed)
    if is_frozen():
        return str(Path(sys.executable).resolve())
    return str(sys.executable)


def agent_cmd(root: Path | None = None, *, trigger: str = "startup", once: bool = False) -> str:
    """Linha de comando para o agente (aspas incluídas no executável)."""
    root = root or project_root()
    args = f"--agent --trigger {trigger}"
    if once:
        args += " --once"

    for name in (APP_EXE, AGENT_EXE):
        exe = root / name
        if exe.exists():
            return f'"{exe}" {args}'

    if is_frozen():
        return f'"{Path(sys.executable).resolve()}" {args}'

    py = _pythonw()
    return f'cmd /c cd /d "{root}" && "{py}" -m entry_app {args}'


def admin_launcher(root: Path | None = None) -> tuple[str, str]:
    """Retorna (target, arguments) para atalho do admin."""
    root = root or project_root()
    for name in (APP_EXE, ADMIN_EXE):
        exe = root / name
        if exe.exists():
            return str(exe), "--admin"
    if is_frozen():
        return str(Path(sys.executable).resolve()), "--admin"
    return str(_pythonw()), "-m entry_app --admin"


def setup_launcher(root: Path | None = None, *, uninstall: bool = False) -> tuple[str, str]:
    root = root or project_root()
    flag = "--wizard uninstall" if uninstall else "--wizard"
    for name in (APP_EXE, SETUP_EXE):
        exe = root / name
        if exe.exists():
            return str(exe), flag
    if is_frozen():
        return str(Path(sys.executable).resolve()), flag
    return str(sys.executable), f"-m entry_app {flag}"


def _pythonw() -> Path:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    if candidate.exists():
        return candidate
    return Path(sys.executable)


def distribution_files(root: Path | None = None) -> list[str]:
    """Arquivos/pastas a copiar na instalação (modo release)."""
    root = root or project_root()
    names = [
        APP_EXE,
        AGENT_EXE,
        ADMIN_EXE,
        SETUP_EXE,
        "VERSION",
        "config",
        "assets",
        "README.md",
        "INSTALAR.cmd",
        "INSTALAR.vbs",
        "DESINSTALAR.cmd",
        "DESINSTALAR.vbs",
        "ADMINISTRAR.cmd",
        "TESTAR_CONFIG.cmd",
        "DesktopManager.cmd",
    ]
    return [n for n in names if (root / n).exists()]
