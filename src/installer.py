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
from .runtime import (
    ADMIN_EXE,
    AGENT_EXE,
    SETUP_EXE,
    admin_launcher,
    agent_cmd,
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
    has_agent_exe = (src / AGENT_EXE).exists()

    if has_agent_exe or is_frozen():
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
        for name in (AGENT_EXE, ADMIN_EXE, SETUP_EXE):
            s = src / name
            if s.exists():
                shutil.copy2(s, dst / name)
    else:
        for name in ("src", "config", "assets", "admin"):
            s = src / name
            if s.exists():
                target = dst / name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(s, target, ignore=ignore)
        for name in ("main.py", "README.md", "entry_agent.py", "entry_admin.py", "entry_setup.py"):
            s = src / name
            if s.exists():
                shutil.copy2(s, dst / name)
        (dst / "src" / "__init__.py").touch(exist_ok=True)

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
        "frozen": has_agent_exe or is_frozen(),
        "executable": sys.executable,
        "version": version,
    }
    (dst / "install.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Arquivos copiados para %s (v%s)", dst, version)
    return dst


def register_startup_run_key(root: Path) -> None:
    if (root / AGENT_EXE).exists():
        value = f'"{root / AGENT_EXE}" --trigger startup'
    else:
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


def register_scheduled_tasks(root: Path) -> bool:
    """Registra início (Run ou tarefa) e desligamento (Agendador).

    Retorna True se o startup ficou ativo (tarefa ou chave Run).
    ONLOGON via schtasks frequentemente retorna 'Acesso negado' sem admin;
    nesse caso usamos HKCU\\...\\Run (padrão confiável por usuário).
    """
    if (root / AGENT_EXE).exists():
        agent = root / AGENT_EXE
        startup_tr = f'"{agent}" --trigger startup'
        shutdown_tr = f'"{agent}" --trigger shutdown --once'
    else:
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

    admin_target, admin_args = admin_launcher(root)
    _write_shortcut(
        programs / "Desktop Manager Admin.lnk",
        admin_target,
        arguments=admin_args,
        workdir=str(root),
        description="Administrar Desktop Manager",
    )

    setup_target, setup_args = setup_launcher(root, uninstall=True)
    _write_shortcut(
        programs / "Desinstalar Desktop Manager.lnk",
        setup_target,
        arguments=setup_args,
        workdir=str(root),
        description="Desinstalar Desktop Manager",
    )


def _write_shortcut(
    lnk: Path,
    target: str,
    arguments: str = "",
    workdir: str = "",
    description: str = "",
) -> None:
    def esc(s: str) -> str:
        return s.replace("'", "''")

    ps = f"""
$WshShell = New-Object -ComObject WScript.Shell
$s = $WshShell.CreateShortcut('{esc(str(lnk))}')
$s.TargetPath = '{esc(target)}'
$s.Arguments = '{esc(arguments)}'
$s.WorkingDirectory = '{esc(workdir)}'
$s.Description = '{esc(description)}'
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

    if (root / AGENT_EXE).exists():
        (root / "run_agent.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{AGENT_EXE}" %*\r\n',
            encoding="utf-8",
        )
        (root / "run_admin.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{ADMIN_EXE}"\r\n',
            encoding="utf-8",
        )
    else:
        from .runtime import _pythonw

        pyw = _pythonw()
        (root / "run_agent.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{pyw}" -m src.agent %*\r\n',
            encoding="utf-8",
        )
        (root / "run_admin.cmd").write_text(
            f'@echo off\r\ncd /d "%~dp0"\r\n"{sys.executable}" -m admin.admin_gui\r\n',
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
    info = status()
    logger.info("Instalação concluída em %s", root)
    print(f"\nDesktop Manager instalado em:\n  {root}")
    print("Atalhos: Menu Iniciar → Desktop Manager")
    if (root / ADMIN_EXE).exists():
        print(f"Admin: {root / ADMIN_EXE}")
    else:
        print("Admin: execute run_admin.cmd ou o atalho do Menu Iniciar")
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


def status() -> dict:
    info = {
        "install_dir": str(install_dir()),
        "installed": install_dir().exists(),
        "frozen_package": (install_dir() / AGENT_EXE).exists(),
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
