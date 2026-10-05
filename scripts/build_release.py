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
        "admin.setup_wizard",
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

    for name in ("desktop-4x3.jpg", "desktop-16x9.jpg"):
        img = ROOT / "assets" / "wallpaper" / name
        if not img.exists():
            raise FileNotFoundError(
                f"Wallpaper padrão ausente: {img}. "
                "Inclua desktop-4x3.jpg e desktop-16x9.jpg em assets/wallpaper/"
            )

    print("Empacotando Agent...")
    agent = _build_exe("entry_agent.py", "DesktopManagerAgent", windowed=True)
    print("Empacotando Admin...")
    admin = _build_exe("entry_admin.py", "DesktopManagerAdmin", windowed=True)
    print("Empacotando Setup (wizard gráfico)...")
    setup = _build_exe("entry_setup.py", "DesktopManagerSetup", windowed=True)

    shutil.copy2(agent, RELEASE / agent.name)
    shutil.copy2(admin, RELEASE / admin.name)
    shutil.copy2(setup, RELEASE / setup.name)

    shutil.copytree(ROOT / "config", RELEASE / "config")
    shutil.copytree(ROOT / "assets", RELEASE / "assets")
    if (ROOT / "README.md").exists():
        shutil.copy2(ROOT / "README.md", RELEASE / "README.md")

    # Atalhos sem janela preta: VBS inicia o wizard windowed
    (RELEASE / "INSTALAR.vbs").write_text(
        'Set sh = CreateObject("WScript.Shell")\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        "dir = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
        'sh.Run """" & dir & "\\DesktopManagerSetup.exe"" --wizard install", 1, False\r\n',
        encoding="ascii",
    )
    (RELEASE / "DESINSTALAR.vbs").write_text(
        'Set sh = CreateObject("WScript.Shell")\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        "dir = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
        'sh.Run """" & dir & "\\DesktopManagerSetup.exe"" --wizard uninstall", 1, False\r\n',
        encoding="ascii",
    )
    _write_cmd(
        RELEASE / "INSTALAR.cmd",
        "@echo off\n"
        "wscript //nologo \"%~dp0INSTALAR.vbs\"\n",
    )
    _write_cmd(
        RELEASE / "DESINSTALAR.cmd",
        "@echo off\n"
        "wscript //nologo \"%~dp0DESINSTALAR.vbs\"\n",
    )
    _write_cmd(
        RELEASE / "ADMINISTRAR.cmd",
        "@echo off\n"
        "start \"\" \"%~dp0DesktopManagerAdmin.exe\"\n",
    )
    _write_cmd(
        RELEASE / "TESTAR_CONFIG.cmd",
        "@echo off\n"
        "start \"\" \"%~dp0DesktopManagerAgent.exe\" --trigger manual --once\n",
    )

    (RELEASE / "LEIA-ME.txt").write_text(
        "Desktop Manager — pacote portátil\n"
        "=================================\n\n"
        "Este computador NÃO precisa ter Python instalado.\n\n"
        "1. Copie esta pasta inteira para o PC destino\n"
        "2. Execute INSTALAR (assistente grafico — sem tela preta)\n"
        "3. Use ADMINISTRAR para configurar\n\n"
        "O plano de fundo 4:3 ou 16:9 e escolhido automaticamente pela resolucao da tela.\n\n"
        "Arquivos:\n"
        "  INSTALAR.vbs / .cmd       - assistente de instalacao\n"
        "  DESINSTALAR.vbs / .cmd    - assistente de remocao\n"
        "  ADMINISTRAR.cmd           - painel de configuracao\n"
        "  TESTAR_CONFIG.cmd         - testa a configuracao (sem arrumar o ambiente)\n"
        "  DesktopManagerSetup.exe   - wizard (Instalar/Desinstalar)\n"
        "  DesktopManagerAgent.exe   - agente em segundo plano\n"
        "  DesktopManagerAdmin.exe   - administracao\n"
        "  config\\settings.json      - configuracao\n"
        "  assets\\wallpaper\\         - desktop-4x3.jpg e desktop-16x9.jpg\n",
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
