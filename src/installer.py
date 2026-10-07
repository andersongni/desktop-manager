"""Instalação, desinstalação e registro de tarefas agendadas."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

from .paths import install_dir, project_root
from .app_icon import app_icon_ico
from .runtime import (
    ADMIN_EXE,
    AGENT_EXE,
    APP_EXE,
    SETUP_EXE,
    admin_launcher,
    agent_cmd,
    app_executable,
    distribution_files,
    is_frozen,
    setup_launcher,
)
from .version import current_version

logger = logging.getLogger(__name__)

# Nomes planos — pastas aninhadas (DesktopManager\...) costumam exigir admin
TASK_STARTUP = "DesktopManagerStartup"
TASK_SHUTDOWN = "DesktopManagerShutdown"
# Nomes antigos (versões anteriores) — limpos na desinstalação
TASK_LEGACY = ("DesktopManager\\Startup", "DesktopManager\\Shutdown")
RUN_VALUE = "DesktopManager"


def copy_to_install_dir(source: Path | None = None, dest: Path | None = None) -> Path:
    src = source or project_root()
    dst = dest or install_dir()
    dst.mkdir(parents=True, exist_ok=True)

    # Preserva configuração do usuário em atualizações / reparos
    settings_dst = dst / "config" / "settings.json"
    settings_backup: str | None = None
    if settings_dst.exists():
        try:
            settings_backup = settings_dst.read_text(encoding="utf-8")
        except OSError:
            settings_backup = None

    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".git",
        ".venv",
        "venv",
        "logs",
        "*.log",
        ".idea",
        ".vscode",
        "build",
        "dist",
        "release",
    )

    # Modo release: só copia exes + config + assets (sem código-fonte)
    release_names = distribution_files(src)
    has_app_exe = (src / APP_EXE).exists() or (src / AGENT_EXE).exists()

    if has_app_exe or is_frozen():
        for name in release_names:
            s = src / name
            t = dst / name
            if s.is_dir():
                if t.exists():
                    shutil.rmtree(t)
                shutil.copytree(s, t, ignore=ignore)
            elif s.is_file():
                shutil.copy2(s, t)
        # Garante exes mesmo se distribution_files filtrou
        for name in (APP_EXE, AGENT_EXE, ADMIN_EXE, SETUP_EXE):
            s = src / name
            if s.exists():
                shutil.copy2(s, dst / name)
        # Se só existir o EXE unificado, espelha nomes legados para atalhos antigos
        app = dst / APP_EXE
        if app.exists():
            for legacy in (AGENT_EXE, ADMIN_EXE, SETUP_EXE):
                target = dst / legacy
                if not target.exists():
                    try:
                        shutil.copy2(app, target)
                    except OSError:
                        pass
    else:
        for name in ("src", "config", "assets", "admin"):
            s = src / name
            if s.exists():
                target = dst / name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(s, target, ignore=ignore)
        for name in (
            "main.py",
            "README.md",
            "entry_app.py",
            "entry_agent.py",
            "entry_admin.py",
            "entry_setup.py",
        ):
            s = src / name
            if s.exists():
                shutil.copy2(s, dst / name)
        (dst / "src" / "__init__.py").touch(exist_ok=True)

    if settings_backup is not None:
        cfg_dir = dst / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        try:
            (cfg_dir / "settings.json").write_text(settings_backup, encoding="utf-8")
            logger.info("Configuração anterior preservada (settings.json)")
        except OSError as exc:
            logger.warning("Não foi possível restaurar settings.json: %s", exc)

    version = current_version(src)
    # Garante VERSION na pasta instalada
    version_file = dst / "VERSION"
    if not version_file.exists() or (src / "VERSION").exists():
        src_ver = src / "VERSION"
        if src_ver.exists():
            shutil.copy2(src_ver, version_file)
        else:
            version_file.write_text(version + "\n", encoding="utf-8")

    meta = {
        "source": str(src),
        "install_dir": str(dst),
        "frozen": has_app_exe or is_frozen(),
        "executable": app_executable(dst) if (has_app_exe or is_frozen()) else sys.executable,
        "version": version,
    }
    (dst / "install.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Arquivos copiados para %s (v%s)", dst, version)
    return dst


def register_startup_run_key(root: Path) -> None:
    value = agent_cmd(root, trigger="startup", once=False)
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, value)
    logger.info("Chave Run registrada")


def unregister_startup_run_key() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, RUN_VALUE)
        logger.info("Chave Run removida")
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Não removeu chave Run: %s", exc)


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except OSError:
        pass
    for name in (TASK_STARTUP, *TASK_LEGACY[:1]):
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", name],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            return True
    return False


def set_autostart(enabled: bool, root: Path | None = None) -> None:
    """Liga/desliga inicialização com o Windows (chave Run + tarefa de logon)."""
    root = root or (install_dir() if install_dir().exists() else project_root())
    if enabled:
        register_startup_run_key(root)
        # Tenta também a tarefa; se falhar, a chave Run já cobre o logon
        try:
            if (root / APP_EXE).exists() or (root / AGENT_EXE).exists() or is_frozen():
                tr = agent_cmd(root, trigger="startup", once=False)
                _schtasks_create(
                    TASK_STARTUP,
                    tr,
                    ["/SC", "ONLOGON", "/RL", "LIMITED", "/IT"],
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Tarefa de logon opcional: %s", exc)
        logger.info("Autostart ativado")
        return

    unregister_startup_run_key()
    for name in (TASK_STARTUP, *TASK_LEGACY[:1]):
        subprocess.run(
            ["schtasks", "/Delete", "/TN", name, "/F"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    logger.info("Autostart desativado")


def register_scheduled_tasks(root: Path) -> bool:
    """Registra início (Run ou tarefa) e desligamento (Agendador).

    Retorna True se o startup ficou ativo (tarefa ou chave Run).
    ONLOGON via schtasks frequentemente retorna 'Acesso negado' sem admin;
    nesse caso usamos HKCU\\...\\Run (padrão confiável por usuário).
    """
    startup_tr = agent_cmd(root, trigger="startup", once=False)
    shutdown_tr = agent_cmd(root, trigger="shutdown", once=True)

    startup_ok = _schtasks_create(
        TASK_STARTUP,
        startup_tr,
        # /IT = só com usuário logado; /RL LIMITED = sem elevação na execução
        ["/SC", "ONLOGON", "/RL", "LIMITED", "/IT"],
    )
    if not startup_ok:
        logger.info("Startup via Agendador indisponível — usando chave Run (HKCU)")
        register_startup_run_key(root)
        startup_ok = True

    shutdown_ok = _schtasks_create(
        TASK_SHUTDOWN,
        shutdown_tr,
        [
            "/SC",
            "ONEVENT",
            "/EC",
            "System",
            "/MO",
            "*[System[Provider[@Name='User32'] and (EventID=1074)]]",
            "/RL",
            "LIMITED",
        ],
    )
    if not shutdown_ok:
        logger.warning(
            "Tarefa de desligamento não criada. O agente residente ainda cobre "
            "WM_ENDSESSION quando estiver em execução."
        )

    return startup_ok


def unregister_scheduled_tasks() -> None:
    for name in (TASK_STARTUP, TASK_SHUTDOWN, *TASK_LEGACY):
        subprocess.run(
            ["schtasks", "/Delete", "/TN", name, "/F"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    logger.info("Tarefas agendadas removidas")


def _schtasks_create(name: str, tr: str, schedule_args: list[str]) -> bool:
    subprocess.run(
        ["schtasks", "/Delete", "/TN", name, "/F"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    cmd = ["schtasks", "/Create", "/TN", name, "/TR", tr, *schedule_args, "/F"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        detail = (result.stdout or "") + (result.stderr or "")
        logger.warning("schtasks %s: %s", name, detail.strip() or f"exit {result.returncode}")
        return False
    logger.info("Tarefa criada: %s", name)
    return True


def create_shortcuts(root: Path) -> None:
    programs = Path(os.environ.get("APPDATA", "")) / (
        r"Microsoft\Windows\Start Menu\Programs\Desktop Manager"
    )
    programs.mkdir(parents=True, exist_ok=True)
    icon = app_icon_ico()
    icon_path = str(icon) if icon else ""

    app_target = app_executable(root)
    _write_shortcut(
        programs / "Desktop Manager.lnk",
        app_target,
        arguments="--agent --no-actions",
        workdir=str(root),
        description="Desktop Manager (bandeja do sistema)",
        icon_path=icon_path,
    )

    admin_target, admin_args = admin_launcher(root)
    _write_shortcut(
        programs / "Desktop Manager Admin.lnk",
        admin_target,
        arguments=admin_args,
        workdir=str(root),
        description="Administrar Desktop Manager",
        icon_path=icon_path,
    )

    setup_target, setup_args = setup_launcher(root, uninstall=False)
    _write_shortcut(
        programs / "Desktop Manager Assistente.lnk",
        setup_target,
        arguments=setup_args,
        workdir=str(root),
        description="Assistente de instalação e atualização",
        icon_path=icon_path,
    )

    setup_target, setup_args = setup_launcher(root, uninstall=True)
    _write_shortcut(
        programs / "Desinstalar Desktop Manager.lnk",
        setup_target,
        arguments=setup_args,
        workdir=str(root),
        description="Desinstalar Desktop Manager",
        icon_path=icon_path,
    )


def _write_shortcut(
    lnk: Path,
    target: str,
    arguments: str = "",
    workdir: str = "",
    description: str = "",
    icon_path: str = "",
) -> None:
    def esc(s: str) -> str:
        return s.replace("'", "''")

    icon_line = f"$s.IconLocation = '{esc(icon_path)},0'" if icon_path else ""
    ps = f"""
$WshShell = New-Object -ComObject WScript.Shell
$s = $WshShell.CreateShortcut('{esc(str(lnk))}')
$s.TargetPath = '{esc(target)}'
$s.Arguments = '{esc(arguments)}'
$s.WorkingDirectory = '{esc(workdir)}'
$s.Description = '{esc(description)}'
{icon_line}
$s.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def install(use_tasks: bool = True) -> Path:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    root = copy_to_install_dir()

    if (root / APP_EXE).exists() or (root / AGENT_EXE).exists():
        exe_name = APP_EXE if (root / APP_EXE).exists() else AGENT_EXE
        (root / "run_agent.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{exe_name}" --agent %*\r\n',
            encoding="utf-8",
        )
        (root / "run_admin.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{exe_name}" --admin\r\n',
            encoding="utf-8",
        )
    else:
        from .runtime import _pythonw

        pyw = _pythonw()
        (root / "run_agent.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{pyw}" -m entry_app --agent %*\r\n',
            encoding="utf-8",
        )
        (root / "run_admin.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{sys.executable}" -m entry_app --admin\r\n',
            encoding="utf-8",
        )

    if use_tasks:
        try:
            register_scheduled_tasks(root)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Registro automático falhou (%s) — usando chave Run", exc)
            register_startup_run_key(root)
    else:
        register_startup_run_key(root)

    create_shortcuts(root)
    _ensure_chrome_after_install()
    info = status()
    logger.info("Instalação concluída em %s", root)
    print(f"\nDesktop Manager instalado em:\n  {root}")
    print("Atalhos: Menu Iniciar → Desktop Manager")
    print(f"App: {app_executable(root)}")
    print("Admin: atalho do Menu Iniciar ou DesktopManager.exe --admin")
    print(
        f"Startup: {'Run (HKCU)' if info.get('run_key') else 'Agendador' if info.get('tasks') else 'NÃO REGISTRADO'}"
    )
    print(f"Tarefas: {', '.join(info.get('tasks') or []) or 'nenhuma'}\n")
    return root


def uninstall() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    unregister_scheduled_tasks()
    unregister_startup_run_key()

    programs = Path(os.environ.get("APPDATA", "")) / (
        r"Microsoft\Windows\Start Menu\Programs\Desktop Manager"
    )
    if programs.exists():
        shutil.rmtree(programs, ignore_errors=True)

    dst = install_dir()
    if dst.exists():
        running_from_install = False
        try:
            running_from_install = Path(sys.executable).resolve().is_relative_to(dst.resolve())
        except (ValueError, OSError):
            pass
        try:
            running_from_install = running_from_install or Path.cwd().resolve().is_relative_to(
                dst.resolve()
            )
        except (ValueError, OSError):
            pass

        if running_from_install or is_frozen():
            bat = Path(os.environ.get("TEMP", ".")) / "dm_uninstall.cmd"
            bat.write_text(
                f'@echo off\r\ntimeout /t 2 /nobreak >nul\r\nrmdir /s /q "{dst}"\r\n'
                f'if exist "{dst}" rmdir /s /q "{dst}"\r\ndel "%~f0"\r\n',
                encoding="utf-8",
            )
            flags = subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags)
            print("Desinstalação agendada. Os arquivos serão removidos em instantes.")
        else:
            shutil.rmtree(dst, ignore_errors=True)
            print(f"Removido: {dst}")
    print("Desktop Manager desinstalado.")


def _ensure_chrome_after_install() -> None:
    """Instala o Chrome e prepara como padrão, conforme config."""
    try:
        from .browser import ensure_browser_installed, set_default_browser
        from .config import load_settings

        settings = load_settings()
        br = settings.get("browser", {})
        ensure = bool(br.get("ensure_installed", True))
        set_default = bool(br.get("set_default", True))
        name = str(br.get("default_browser", "chrome")).lower()

        if not ensure and not set_default:
            return

        if set_default:
            result = set_default_browser(
                name,
                open_settings=True,
                install_if_missing=ensure,
            )
        else:
            result = ensure_browser_installed(name)
        logger.info("Navegador na instalação: %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Não foi possível garantir o Chrome na instalação: %s", exc)


def status() -> dict:
    info = {
        "install_dir": str(install_dir()),
        "installed": install_dir().exists(),
        "frozen_package": (install_dir() / APP_EXE).exists()
        or (install_dir() / AGENT_EXE).exists(),
        "version": current_version(install_dir() if install_dir().exists() else None),
        "run_key": False,
        "tasks": [],
    }
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            info["run_key"] = True
    except OSError:
        pass

    for name in (TASK_STARTUP, TASK_SHUTDOWN, *TASK_LEGACY):
        r = subprocess.run(
            ["schtasks", "/Query", "/TN", name],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            info["tasks"].append(name)
    return info



def main(argv: list[str] | None = None) -> int:
    """CLI do instalador (use --cli no entry_setup para forçar este modo)."""
    parser = argparse.ArgumentParser(description="Instalador do Desktop Manager (CLI)")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--install", action="store_true", help="Instalar e registrar no Windows")
    g.add_argument("--uninstall", action="store_true", help="Desinstalar")
    g.add_argument("--status", action="store_true", help="Mostrar status da instalação")
    parser.add_argument(
        "--use-run-key",
        action="store_true",
        help="Usar chave Run em vez do Agendador de Tarefas",
    )
    args = parser.parse_args(argv)

    if args.install:
        install(use_tasks=not args.use_run_key)
    elif args.uninstall:
        uninstall()
    elif args.status:
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
