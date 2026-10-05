"""Gera pacote standalone (.exe) — o PC destino NÃO precisa de Python.

Uso (só na máquina de desenvolvimento):
    python scripts/build_release.py

Saída:
    release/DesktopManager/
        DesktopManagerAgent.exe
        DesktopManagerAdmin.exe
        DesktopManagerSetup.exe
        config/
        assets/
        INSTALAR.cmd
        ...
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "release" / "DesktopManager"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Instalando PyInstaller (apenas nesta máquina de build)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])


def _build_exe(entry: str, name: str, *, windowed: bool) -> Path:
    """Gera um executável onefile em dist/."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        f"--name={name}",
        f"--distpath={DIST}",
        f"--workpath={BUILD / name}",
        f"--specpath={BUILD}",
        "--paths",
        str(ROOT),
    ]
    if windowed:
        cmd.append("--windowed")
    else:
        cmd.append("--console")

    # Oculta imports que o analisador pode perder
    hidden = [
        "src",
        "src.agent",
        "src.actions",
        "src.browser",
        "src.config",
        "src.installer",
        "src.logging_setup",
        "src.organizer",
        "src.paths",
        "src.runtime",
        "src.taskbar",
        "src.wallpaper",
        "admin",
        "admin.admin_gui",
    ]
    for mod in hidden:
        cmd.extend(["--hidden-import", mod])

    cmd.append(str(ROOT / entry))
    print("\n>>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    exe = DIST / f"{name}.exe"
    if not exe.exists():
        raise FileNotFoundError(exe)
    return exe


def _write_cmd(path: Path, body: str) -> None:
    path.write_text(body.replace("\n", "\r\n"), encoding="utf-8")


def assemble() -> Path:
    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    RELEASE.mkdir(parents=True)

    # Garante wallpaper
    bmp = ROOT / "assets" / "wallpaper" / "desktop.bmp"
    if not bmp.exists():
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "make_wallpaper.py")])

    print("Empacotando Agent...")
    agent = _build_exe("entry_agent.py", "DesktopManagerAgent", windowed=True)
    print("Empacotando Admin...")
    admin = _build_exe("entry_admin.py", "DesktopManagerAdmin", windowed=True)
    print("Empacotando Setup...")
    setup = _build_exe("entry_setup.py", "DesktopManagerSetup", windowed=False)

    shutil.copy2(agent, RELEASE / agent.name)
    shutil.copy2(admin, RELEASE / admin.name)
    shutil.copy2(setup, RELEASE / setup.name)

    shutil.copytree(ROOT / "config", RELEASE / "config")
    shutil.copytree(ROOT / "assets", RELEASE / "assets")
    if (ROOT / "README.md").exists():
        shutil.copy2(ROOT / "README.md", RELEASE / "README.md")

    _write_cmd(
        RELEASE / "INSTALAR.cmd",
        "@echo off\n"
        "cd /d \"%~dp0\"\n"
        "echo.\n"
        "echo === Desktop Manager — Instalacao (sem Python) ===\n"
        "echo.\n"
        "DesktopManagerSetup.exe --install\n"
        "echo.\n"
        "pause\n",
    )
    _write_cmd(
        RELEASE / "DESINSTALAR.cmd",
        "@echo off\n"
        "cd /d \"%~dp0\"\n"
        "echo.\n"
        "echo === Desktop Manager — Desinstalacao ===\n"
        "echo.\n"
        "DesktopManagerSetup.exe --uninstall\n"
        "pause\n",
    )
    _write_cmd(
        RELEASE / "ADMINISTRAR.cmd",
        "@echo off\n"
        "cd /d \"%~dp0\"\n"
        "start \"\" DesktopManagerAdmin.exe\n",
    )
    _write_cmd(
        RELEASE / "EXECUTAR_AGORA.cmd",
        "@echo off\n"
        "cd /d \"%~dp0\"\n"
        "DesktopManagerAgent.exe --trigger manual --once\n"
        "pause\n",
    )

    (RELEASE / "LEIA-ME.txt").write_text(
        "Desktop Manager — pacote portátil\n"
        "=================================\n\n"
        "Este computador NÃO precisa ter Python instalado.\n\n"
        "1. Copie esta pasta inteira para o PC destino\n"
        "2. (Opcional) Substitua assets\\wallpaper\\desktop.bmp pela sua imagem\n"
        "3. Execute INSTALAR.cmd\n"
        "4. Use ADMINISTRAR.cmd para configurar\n\n"
        "Arquivos:\n"
        "  INSTALAR.cmd              — instala e registra no Windows\n"
        "  DESINSTALAR.cmd           — remove\n"
        "  ADMINISTRAR.cmd           — painel de configuração\n"
        "  EXECUTAR_AGORA.cmd        — roda as ações uma vez\n"
        "  DesktopManagerAgent.exe   — agente em segundo plano\n"
        "  DesktopManagerAdmin.exe   — administração\n"
        "  DesktopManagerSetup.exe   — instalador\n"
        "  config\\settings.json      — configuração\n"
        "  assets\\wallpaper\\         — imagem de fundo\n",
        encoding="utf-8",
    )

    print(f"\nPacote pronto:\n  {RELEASE}")
    print("Copie a pasta release\\DesktopManager para o PC sem Python e rode INSTALAR.cmd")
    return RELEASE


def main() -> int:
    _ensure_pyinstaller()
    assemble()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
