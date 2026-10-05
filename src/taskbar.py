"""Fixar / desafixar atalhos na barra de tarefas do Windows."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def apply_taskbar_actions(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Aplica listas de pin/unpin da configuração."""
    report: list[dict[str, str]] = []
    for path in settings.get("unpin", []):
        report.append(_invoke_verb(Path(path), unpin=True))
    for path in settings.get("pin", []):
        report.append(_invoke_verb(Path(path), unpin=False))
    return report


def pin(path: str | Path) -> dict[str, str]:
    return _invoke_verb(Path(path), unpin=False)


def unpin(path: str | Path) -> dict[str, str]:
    return _invoke_verb(Path(path), unpin=True)


def _invoke_verb(target: Path, unpin: bool) -> dict[str, str]:
    """Usa Shell.Application para pin/unpin.

    Observação: no Windows 10 (1607+) e Windows 11 o verbo de *fixar*
    pode estar bloqueado pela política da Microsoft. Desafixar costuma
    funcionar. Em caso de falha, o relatório indica o motivo.
    """
    target = target.expanduser().resolve()
    action = "unpin" if unpin else "pin"
    if not target.exists():
        msg = f"Arquivo não encontrado: {target}"
        logger.warning(msg)
        return {"path": str(target), "action": action, "status": "error", "detail": msg}

    # Verbos conhecidos (variação por idioma do Windows)
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
    # Escape single quotes for PowerShell literal path
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
