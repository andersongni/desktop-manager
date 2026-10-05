"""Navegador padrão e limpeza de dados de navegação."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BROWSER_EXES: dict[str, list[str]] = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        str(Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe"),
    ],
}

# Pastas de dados por navegador (relativas a LOCALAPPDATA ou APPDATA)
BROWSER_DATA: dict[str, dict[str, list[Path]]] = {
    "chrome": {
        "cache": [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Cache",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Code Cache",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/GPUCache",
        ],
        "cookies": [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Network/Cookies",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/Cookies",
        ],
        "history": [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/History",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data/Default/History Provider Cache",
        ],
    },
    "edge": {
        "cache": [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/Cache",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/Code Cache",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/GPUCache",
        ],
        "cookies": [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/Network/Cookies",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/Cookies",
        ],
        "history": [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data/Default/History",
        ],
    },
    "firefox": {
        "cache": [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Mozilla/Firefox/Profiles",
        ],
        "cookies": [
            Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox/Profiles",
        ],
        "history": [
            Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox/Profiles",
        ],
    },
    "brave": {
        "cache": [
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "BraveSoftware/Brave-Browser/User Data/Default/Cache",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "BraveSoftware/Brave-Browser/User Data/Default/Code Cache",
        ],
        "cookies": [
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "BraveSoftware/Brave-Browser/User Data/Default/Network/Cookies",
        ],
        "history": [
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "BraveSoftware/Brave-Browser/User Data/Default/History",
        ],
    },
}

PROCESS_NAMES = {
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "brave": "brave.exe",
}


def find_browser_exe(name: str) -> Path | None:
    for candidate in BROWSER_EXES.get(name.lower(), []):
        p = Path(candidate)
        if p.exists():
            return p
    return None


def set_default_browser(name: str, open_settings: bool = True) -> dict[str, Any]:
    """Tenta preparar o navegador padrão.

    No Windows 10/11 a escolha definitiva exige confirmação do usuário
    nas Configurações. Este método:
      1. Localiza o executável
      2. Registra App Paths (quando possível)
      3. Abre a tela de apps padrão para o usuário confirmar
    """
    name = name.lower()
    exe = find_browser_exe(name)
    if exe is None:
        raise FileNotFoundError(f"Navegador '{name}' não encontrado neste computador")

    result: dict[str, Any] = {"browser": name, "exe": str(exe), "settings_opened": False}

    # Abre a UI oficial — única forma confiável e suportada no Win10/11
    if open_settings:
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "ms-settings:defaultapps"],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            result["settings_opened"] = True
            result["message"] = (
                f"Selecione '{_display_name(name)}' como navegador padrão nas Configurações."
            )
            logger.info("Configurações de apps padrão abertas para: %s", name)
        except OSError as exc:
            logger.warning("Não foi possível abrir Configurações: %s", exc)
            result["message"] = str(exc)

    # Também registra como preferência interna do Desktop Manager
    try:
        key_path = r"Software\DesktopManager"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "PreferredBrowser", 0, winreg.REG_SZ, name)
            winreg.SetValueEx(key, "PreferredBrowserExe", 0, winreg.REG_SZ, str(exe))
    except OSError as exc:
        logger.debug("Registro de preferência: %s", exc)

    return result


def clear_browsing_data(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Remove cache/cookies/histórico conforme configuração."""
    browsers = [b.lower() for b in settings.get("browsers", [])]
    clear_cache = settings.get("clear_cache", True)
    clear_cookies = settings.get("clear_cookies", False)
    clear_history = settings.get("clear_history", False)

    report: list[dict[str, str]] = []
    for browser in browsers:
        if _is_browser_running(browser):
            msg = f"{browser}: feche o navegador antes de limpar os dados"
            logger.warning(msg)
            report.append({"browser": browser, "status": "skipped", "detail": msg})
            continue

        targets: list[Path] = []
        data = BROWSER_DATA.get(browser, {})
        if clear_cache:
            targets.extend(data.get("cache", []))
        if clear_cookies:
            targets.extend(data.get("cookies", []))
        if clear_history:
            targets.extend(data.get("history", []))

        if browser == "firefox":
            cleared = _clear_firefox(clear_cache, clear_cookies, clear_history)
            report.append({"browser": browser, "status": "ok", "detail": cleared})
            continue

        removed = 0
        for target in targets:
            removed += _remove_path(target)
        detail = f"{removed} item(ns) removido(s)"
        logger.info("%s: %s", browser, detail)
        report.append({"browser": browser, "status": "ok", "detail": detail})

    return report


def _display_name(name: str) -> str:
    return {
        "chrome": "Google Chrome",
        "edge": "Microsoft Edge",
        "firefox": "Mozilla Firefox",
        "brave": "Brave",
    }.get(name, name)


def _is_browser_running(browser: str) -> bool:
    proc = PROCESS_NAMES.get(browser)
    if not proc:
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {proc}", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return proc.lower() in out.lower()
    except (subprocess.CalledProcessError, OSError):
        return False


def _remove_path(path: Path) -> int:
    count = 0
    if not path.exists():
        return 0
    try:
        if path.is_file():
            path.unlink(missing_ok=True)
            return 1
        for child in path.iterdir():
            try:
                if child.is_file() or child.is_symlink():
                    child.unlink(missing_ok=True)
                    count += 1
                elif child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    count += 1
            except OSError as exc:
                logger.debug("Ignorado %s: %s", child, exc)
    except OSError as exc:
        logger.debug("Falha em %s: %s", path, exc)
    return count


def _clear_firefox(cache: bool, cookies: bool, history: bool) -> str:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Mozilla/Firefox/Profiles"
    roaming = Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox/Profiles"
    removed = 0
    if cache and local.exists():
        for profile in local.iterdir():
            if profile.is_dir():
                for name in ("cache2", "startupCache", "thumbnails"):
                    removed += _remove_path(profile / name)
    if roaming.exists():
        for profile in roaming.iterdir():
            if not profile.is_dir():
                continue
            if cookies:
                removed += _remove_path(profile / "cookies.sqlite")
            if history:
                removed += _remove_path(profile / "places.sqlite")
    return f"{removed} item(ns) removido(s)"
