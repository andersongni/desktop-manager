"""Gera pacote standalone (.exe) — o PC destino NÃO precisa de Python.

Uso (só na máquina de desenvolvimento):
    python scripts/build_release.py

Saída:
    release/DesktopManager/
        DesktopManager.exe   ← instalador/atualizador + agente + admin
        config/
        assets/
        INSTALAR.cmd
        ...
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "release" / "DesktopManager"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON = ROOT / "assets" / "icon" / "app.ico"


def package_version() -> str:
    env = (os.environ.get("DESKTOP_MANAGER_VERSION") or "").strip().lstrip("vV")
    if env:
        return env
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return out.lstrip("vV")
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        pass
    sys.path.insert(0, str(ROOT))
    from src import __version__

    return str(__version__).lstrip("vV")


def _ensure_deps() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Instalando PyInstaller…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Instalando Pillow…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "-q"])


def _ensure_icon() -> Path:
    if not ICON.exists():
        print("Gerando ícone…")
        subprocess.check_call([sys.executable, str(ROOT / "scripts" / "make_icon.py")], cwd=ROOT)
    if not ICON.exists():
        raise FileNotFoundError(f"Ícone ausente: {ICON}")
    return ICON


def _build_exe(entry: str, name: str, *, windowed: bool) -> Path:
    """Gera um executável onefile em dist/."""
    icon = _ensure_icon()
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
        f"--icon={icon}",
        "--add-data",
        f"{ROOT / 'assets' / 'icon'};assets/icon",
    ]
    if windowed:
        cmd.append("--windowed")
    else:
        cmd.append("--console")

    hidden = [
        "src",
        "src.agent",
        "src.actions",
        "src.app_icon",
        "src.browser",
        "src.config",
        "src.installer",
        "src.logging_setup",
        "src.organizer",
        "src.paths",
        "src.runtime",
        "src.taskbar",
        "src.tray",
        "src.wallpaper",
        "src.updater",
        "src.version",
        "admin",
        "admin.admin_gui",
        "admin.setup_wizard",
        "entry_app",
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

    version = package_version()
    print(f"Versão do pacote: {version}")

    for name in ("desktop-4x3.jpg", "desktop-16x9.jpg"):
        img = ROOT / "assets" / "wallpaper" / name
        if not img.exists():
            raise FileNotFoundError(
                f"Wallpaper padrão ausente: {img}. "
                "Inclua desktop-4x3.jpg e desktop-16x9.jpg em assets/wallpaper/"
            )

    print("Empacotando DesktopManager.exe (wizard + agente + admin)…")
    app = _build_exe("entry_app.py", "DesktopManager", windowed=True)

    shutil.copy2(app, RELEASE / app.name)
    # Compatibilidade com atalhos/scripts antigos
    for legacy in (
        "DesktopManagerAgent.exe",
        "DesktopManagerAdmin.exe",
        "DesktopManagerSetup.exe",
    ):
        shutil.copy2(app, RELEASE / legacy)

    (RELEASE / "VERSION").write_text(version + "\n", encoding="utf-8")
    shutil.copytree(ROOT / "config", RELEASE / "config")
    shutil.copytree(ROOT / "assets", RELEASE / "assets")
    if (ROOT / "README.md").exists():
        shutil.copy2(ROOT / "README.md", RELEASE / "README.md")

    (RELEASE / "INSTALAR.vbs").write_text(
        'Set sh = CreateObject("WScript.Shell")\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        "dir = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
        'sh.Run """" & dir & "\\DesktopManager.exe"" --wizard install", 1, False\r\n',
        encoding="ascii",
    )
    (RELEASE / "DESINSTALAR.vbs").write_text(
        'Set sh = CreateObject("WScript.Shell")\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        "dir = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
        'sh.Run """" & dir & "\\DesktopManager.exe"" --wizard uninstall", 1, False\r\n',
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
        "start \"\" \"%~dp0DesktopManager.exe\" --admin\n",
    )
    _write_cmd(
        RELEASE / "DesktopManager.cmd",
        "@echo off\n"
        "start \"\" \"%~dp0DesktopManager.exe\" %*\n",
    )
    _write_cmd(
        RELEASE / "TESTAR_CONFIG.cmd",
        "@echo off\n"
        "start \"\" \"%~dp0DesktopManager.exe\" --agent --trigger manual --once\n",
    )

    (RELEASE / "LEIA-ME.txt").write_text(
        "Desktop Manager — executável standalone\n"
        "======================================\n\n"
        "Este computador NÃO precisa ter Python instalado.\n\n"
        "1. Execute DesktopManager.exe (ou INSTALAR)\n"
        "2. Siga o assistente (wizard) de instalação/atualização\n"
        "3. O programa fica na área de notificação (bandeja)\n\n"
        "No ícone da bandeja você pode:\n"
        "  - Abrir configurações\n"
        "  - Executar ações agora\n"
        "  - Verificar atualizações\n"
        "  - Ligar/desligar inicialização com o Windows\n"
        "  - Abrir o assistente\n"
        "  - Encerrar o programa\n\n"
        "Arquivos:\n"
        "  DesktopManager.exe        - app completo (wizard + agente + admin)\n"
        "  INSTALAR.vbs / .cmd       - atalho para o wizard de instalação\n"
        "  DESINSTALAR.vbs / .cmd    - atalho para remoção\n"
        "  ADMINISTRAR.cmd           - painel de configuração\n"
        "  config\\settings.json      - configuração\n"
        "  assets\\icon\\              - ícone do aplicativo\n"
        "  assets\\wallpaper\\         - planos de fundo\n"
        f"  VERSION                   - {version}\n",
        encoding="utf-8",
    )

    print(f"\nPacote pronto (v{version}):\n  {RELEASE}")
    print("Execute release\\DesktopManager\\DesktopManager.exe")
    return RELEASE


def main() -> int:
    _ensure_deps()
    _ensure_icon()
    assemble()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
