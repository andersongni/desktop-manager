"""Fixar ícones na barra de tarefas do Windows (ordem definida)."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import winreg
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .browser import find_browser_exe

logger = logging.getLogger(__name__)

# Ordem padrão solicitada: Explorer → Word → Excel → PowerPoint → Chrome
DEFAULT_PIN_ORDER = ("explorer", "word", "excel", "powerpoint", "chrome")

OFFICE_EXES = {
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
}

OFFICE_LNK_NAMES = {
    "word": ("Word.lnk", "Microsoft Word.lnk", "Word 2016.lnk", "Word 2019.lnk", "Word 2021.lnk"),
    "excel": ("Excel.lnk", "Microsoft Excel.lnk", "Excel 2016.lnk", "Excel 2019.lnk", "Excel 2021.lnk"),
    "powerpoint": (
        "PowerPoint.lnk",
        "Microsoft PowerPoint.lnk",
        "PowerPoint 2016.lnk",
        "PowerPoint 2019.lnk",
        "PowerPoint 2021.lnk",
    ),
}


def apply_taskbar_actions(settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Aplica a configuração da barra de tarefas.

    Preferência:
      - settings['pins'] = lista ordenada de ids (explorer, word, ...)
      - settings['replace'] = True → só esses ícones (Remove defaults)
    Compatibilidade: ainda aceita pin/unpin com caminhos absolutos.
    """
    report: list[dict[str, Any]] = []

    pins = settings.get("pins")
    if pins is None and not settings.get("pin") and not settings.get("unpin"):
        pins = list(DEFAULT_PIN_ORDER)

    if pins is not None:
        replace = bool(settings.get("replace", True))
        report.extend(apply_ordered_pins(list(pins), replace=replace))
        return report

    for path in settings.get("unpin", []):
        report.append(_invoke_verb(Path(path), unpin=True))
    for path in settings.get("pin", []):
        report.append(_invoke_verb(Path(path), unpin=False))
    return report


def apply_ordered_pins(pin_ids: list[str], *, replace: bool = True) -> list[dict[str, Any]]:
    """Define a barra de tarefas com os apps na ordem dada."""
    report: list[dict[str, Any]] = []
    resolved: list[tuple[str, Path]] = []

    for app_id in pin_ids:
        path = resolve_app_path(app_id)
        if path is None:
            report.append(
                {
                    "app": app_id,
                    "action": "resolve",
                    "status": "error",
                    "detail": "aplicativo não encontrado neste computador",
                }
            )
            logger.warning("App da taskbar não encontrado: %s", app_id)
            continue
        resolved.append((app_id, path))
        report.append(
            {
                "app": app_id,
                "action": "resolve",
                "status": "ok",
                "detail": str(path),
            }
        )

    if not resolved:
        report.append(
            {
                "action": "apply",
                "status": "error",
                "detail": "nenhum aplicativo resolvido — barra não alterada",
            }
        )
        return report

    shortcuts_dir = _pins_dir()
    shortcuts_dir.mkdir(parents=True, exist_ok=True)
    # Limpa atalhos antigos nossos
    for old in shortcuts_dir.glob("*.lnk"):
        old.unlink(missing_ok=True)

    link_paths: list[Path] = []
    for index, (app_id, target) in enumerate(resolved, start=1):
        lnk = shortcuts_dir / f"{index:02d}-{app_id}.lnk"
        _create_shortcut(lnk, target)
        link_paths.append(lnk)

    xml_path = _write_layout_xml(link_paths, replace=replace)
    report.append({"action": "layout_xml", "status": "ok", "detail": str(xml_path)})

    reset = _reset_taskbar_layout()
    report.append(reset)

    # Fallback: tenta verbs de pin na ordem (Win10 antigo / quando layout não aplica)
    for lnk in link_paths:
        pin_result = _invoke_verb(lnk, unpin=False)
        pin_result["app"] = lnk.stem
        report.append(pin_result)

    logger.info(
        "Taskbar configurada (%d apps, replace=%s): %s",
        len(resolved),
        replace,
        " → ".join(a for a, _ in resolved),
    )
    return report


def resolve_app_path(app_id: str) -> Path | None:
    """Localiza o executável (ou .lnk) do app conhecido."""
    key = app_id.lower().strip()
    if key == "explorer":
        return Path(os.environ.get("WINDIR", r"C:\Windows")) / "explorer.exe"

    if key == "chrome":
        return find_browser_exe("chrome")

    if key in OFFICE_EXES:
        found = _find_office_exe(key)
        if found:
            return found
        found_lnk = _find_start_menu_lnk(OFFICE_LNK_NAMES[key])
        if found_lnk:
            return found_lnk
        return None

    # Caminho absoluto passado diretamente
    p = Path(app_id)
    if p.exists():
        return p
    return None


def pin(path: str | Path) -> dict[str, str]:
    return _invoke_verb(Path(path), unpin=False)


def unpin(path: str | Path) -> dict[str, str]:
    return _invoke_verb(Path(path), unpin=True)


def _pins_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "DesktopManager" / "taskbar-pins"


def _shell_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Shell"


def _find_office_exe(app_id: str) -> Path | None:
    exe_name = OFFICE_EXES[app_id]
    candidates: list[Path] = []

    # Registro App Paths (mais rápido / confiável)
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sub in (
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
            rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
        ):
            try:
                with winreg.OpenKey(hive, sub) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    if value:
                        candidates.append(Path(value))
            except OSError:
                pass

    # Caminhos clássicos Click-to-Run / MSI
    bases = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Office",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Office",
    ]
    for base in bases:
        for rel in (
            Path("root") / "Office16" / exe_name,
            Path("root") / "Office15" / exe_name,
            Path("Office16") / exe_name,
            Path("Office15") / exe_name,
        ):
            candidates.append(base / rel)
        # fallback amplo
        office16 = base / "root" / "Office16" / exe_name
        if not office16.exists() and base.exists():
            candidates.extend(base.rglob(exe_name))

    for c in candidates:
        if c.exists():
            return c
    return None


def _find_start_menu_lnk(names: tuple[str, ...]) -> Path | None:
    roots = [
        Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            for hit in root.rglob(name):
                return hit
    return None


def _create_shortcut(lnk: Path, target: Path) -> None:
    target_ps = str(target).replace("'", "''")
    lnk_ps = str(lnk).replace("'", "''")
    workdir = str(target.parent if target.suffix.lower() == ".exe" else target).replace("'", "''")
    ps = f"""
$Wsh = New-Object -ComObject WScript.Shell
$s = $Wsh.CreateShortcut('{lnk_ps}')
$s.TargetPath = '{target_ps}'
$s.WorkingDirectory = '{workdir}'
$s.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=30,
        check=False,
    )
    if not lnk.exists():
        raise OSError(f"Falha ao criar atalho: {lnk}")


def _write_layout_xml(link_paths: list[Path], *, replace: bool) -> Path:
    placement = ' PinListPlacement="Replace"' if replace else ""
    pins_xml = []
    for lnk in link_paths:
        stem = lnk.stem.lower()  # ex: 01-explorer
        if stem.endswith("-explorer") or stem == "explorer":
            pins_xml.append(
                '        <taskbar:DesktopApp DesktopApplicationID="Microsoft.Windows.Explorer"/>'
            )
        else:
            path_attr = escape(str(lnk))
            pins_xml.append(
                f'        <taskbar:DesktopApp DesktopApplicationLinkPath="{path_attr}"/>'
            )

    body = "\n".join(pins_xml)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<LayoutModificationTemplate
    xmlns="http://schemas.microsoft.com/Start/2014/LayoutModification"
    xmlns:defaultlayout="http://schemas.microsoft.com/Start/2014/FullDefaultLayout"
    xmlns:start="http://schemas.microsoft.com/Start/2014/StartLayout"
    xmlns:taskbar="http://schemas.microsoft.com/Start/2014/TaskbarLayout"
    Version="1">
  <CustomTaskbarLayoutCollection{placement}>
    <defaultlayout:TaskbarLayout>
      <taskbar:TaskbarPinList>
{body}
      </taskbar:TaskbarPinList>
    </defaultlayout:TaskbarLayout>
  </CustomTaskbarLayoutCollection>
</LayoutModificationTemplate>
"""
    shell = _shell_dir()
    shell.mkdir(parents=True, exist_ok=True)
    path = shell / "LayoutModification.xml"
    path.write_text(xml, encoding="utf-8")
    logger.info("LayoutModification.xml escrito: %s", path)
    return path


def _reset_taskbar_layout() -> dict[str, Any]:
    """Limpa pins atuais e reinicia o Explorer para aplicar o layout."""
    pinned = (
        Path(os.environ.get("APPDATA", ""))
        / "Microsoft"
        / "Internet Explorer"
        / "Quick Launch"
        / "User Pinned"
        / "TaskBar"
    )
    removed = 0
    if pinned.exists():
        for item in pinned.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                    removed += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    removed += 1
            except OSError as exc:
                logger.debug("Não removeu %s: %s", item, exc)

    # Cache de layout / taskband
    shell = _shell_dir()
    for pattern in ("*.dat", "DefaultLayouts.xml"):
        for f in shell.glob(pattern):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Taskband")
    except FileNotFoundError:
        pass
    except OSError:
        # Pode ter subchaves — remove recursivo via PowerShell
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Remove-Item -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Taskband' -Recurse -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    # Reinicia Explorer
    subprocess.run(
        ["taskkill", "/F", "/IM", "explorer.exe"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    time.sleep(1.2)
    subprocess.Popen(
        ["explorer.exe"],
        creationflags=subprocess.CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0),
    )

    return {
        "action": "reset_taskbar",
        "status": "ok",
        "detail": f"pins antigos removidos={removed}; explorer reiniciado",
    }


def _invoke_verb(target: Path, unpin: bool) -> dict[str, str]:
    """Usa Shell.Application para pin/unpin (fallback)."""
    target = target.expanduser().resolve()
    action = "unpin" if unpin else "pin"
    if not target.exists():
        msg = f"Arquivo não encontrado: {target}"
        logger.warning(msg)
        return {"path": str(target), "action": action, "status": "error", "detail": msg}

    if unpin:
        verbs = [
            "Unpin from taskbar",
            "Desafixar da barra de tarefas",
            "taskbarunpin",
        ]
    else:
        verbs = [
            "Pin to taskbar",
            "Fixar na barra de tarefas",
            "taskbarpin",
        ]

    verbs_ps = "@(" + ",".join(f"'{v}'" for v in verbs) + ")"
    target_ps = str(target).replace("'", "''")
    ps_script = f"""
$ErrorActionPreference = 'Stop'
$TargetPath = '{target_ps}'
$Verbs = {verbs_ps}
$shell = New-Object -ComObject Shell.Application
$folder = Split-Path -LiteralPath $TargetPath
$name = Split-Path -LiteralPath $TargetPath -Leaf
$ns = $shell.Namespace($folder)
if (-not $ns) {{ throw "Pasta invalida: $folder" }}
$item = $ns.ParseName($name)
if (-not $item) {{ throw "Item invalido: $name" }}
$available = @($item.Verbs() | ForEach-Object {{ $_.Name -replace '&','' }})
foreach ($v in $Verbs) {{
  $verb = $item.Verbs() | Where-Object {{ ($_.Name -replace '&','') -eq $v -or $_.Name -eq $v }}
  if ($verb) {{
    $verb.DoIt()
    Write-Output "OK:$v"
    exit 0
  }}
}}
Write-Output ("FAIL:" + ($available -join '|'))
exit 2
"""
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = (completed.stdout or "").strip()
        if completed.returncode == 0 and output.startswith("OK:"):
            logger.info("%s OK: %s", action, target)
            return {
                "path": str(target),
                "action": action,
                "status": "ok",
                "detail": output,
            }

        detail = output or (completed.stderr or "verbo indisponível neste Windows")
        logger.warning("%s falhou para %s: %s", action, target, detail)
        return {
            "path": str(target),
            "action": action,
            "status": "error",
            "detail": detail,
        }
    except (subprocess.SubprocessError, OSError) as exc:
        logger.error("Erro ao %s %s: %s", action, target, exc)
        return {
            "path": str(target),
            "action": action,
            "status": "error",
            "detail": str(exc),
        }
