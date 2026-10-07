"""Atualização automática a partir das GitHub Releases."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .paths import install_dir, project_root
from .runtime import ADMIN_EXE, AGENT_EXE, APP_EXE, SETUP_EXE, is_frozen
from .version import current_version, is_newer, normalize_version

logger = logging.getLogger(__name__)

DEFAULT_REPO = "andersongni/desktop-manager"
USER_AGENT = "DesktopManager-Updater"
ASSET_PREFIX = "desktop-manager-windows-x64-"
STATE_NAME = "update_state.json"


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    name: str
    download_url: str
    html_url: str
    published_at: str


@dataclass
class UpdateResult:
    status: str  # up_to_date | available | downloaded | applied | scheduled | skipped | error
    local_version: str
    remote_version: str = ""
    detail: str = ""
    release: ReleaseInfo | None = None


def _updates_cfg(settings: dict[str, Any] | None) -> dict[str, Any]:
    cfg = (settings or {}).get("updates") or {}
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "auto_apply": bool(cfg.get("auto_apply", True)),
        "check_interval_hours": float(cfg.get("check_interval_hours", 6)),
        "github_repo": str(cfg.get("github_repo") or DEFAULT_REPO).strip(),
    }


def _state_path() -> Path:
    return install_dir() / STATE_NAME


def _load_state() -> dict[str, Any]:
    path = _state_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(data: dict[str, Any]) -> None:
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("Não salvou estado de update: %s", exc)


def _http_get_json(url: str, timeout: float = 30) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_download(url: str, dest: Path, timeout: float = 120) -> None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def fetch_latest_release(repo: str = DEFAULT_REPO) -> ReleaseInfo:
    data = _http_get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    tag = str(data.get("tag_name") or "")
    version = normalize_version(tag)
    assets = data.get("assets") or []
    asset = None
    for item in assets:
        name = str(item.get("name") or "")
        if name.startswith(ASSET_PREFIX) and name.lower().endswith(".zip"):
            asset = item
            break
    if asset is None:
        for item in assets:
            name = str(item.get("name") or "")
            if name.lower().endswith(".zip"):
                asset = item
                break
    if asset is None:
        raise RuntimeError(f"Release {tag} sem asset .zip")
    url = str(asset.get("browser_download_url") or "")
    if not url:
        raise RuntimeError("Asset sem URL de download")
    return ReleaseInfo(
        tag=tag,
        version=version,
        name=str(asset.get("name") or ""),
        download_url=url,
        html_url=str(data.get("html_url") or ""),
        published_at=str(data.get("published_at") or ""),
    )


def _has_app_binary(root: Path) -> bool:
    return (root / APP_EXE).exists() or (root / AGENT_EXE).exists()


def target_install_root() -> Path:
    """Pasta que deve receber a atualização (preferência: instalação LOCALAPPDATA)."""
    installed = install_dir()
    if _has_app_binary(installed):
        return installed
    if is_frozen():
        return project_root()
    return installed


def can_apply_update() -> bool:
    return _has_app_binary(target_install_root())


def check_for_update(
    settings: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> UpdateResult:
    cfg = _updates_cfg(settings)
    local = current_version()
    if not cfg["enabled"] and not force:
        return UpdateResult(status="skipped", local_version=local, detail="atualizações desabilitadas")

    state = _load_state()
    interval = max(0.25, float(cfg["check_interval_hours"])) * 3600
    last = float(state.get("last_check_ts") or 0)
    if not force and last and (time.time() - last) < interval:
        return UpdateResult(
            status="skipped",
            local_version=local,
            remote_version=str(state.get("last_remote_version") or ""),
            detail=f"última verificação há menos de {cfg['check_interval_hours']}h",
        )

    try:
        release = fetch_latest_release(cfg["github_repo"])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, OSError) as exc:
        logger.warning("Falha ao consultar releases: %s", exc)
        return UpdateResult(status="error", local_version=local, detail=str(exc))

    state["last_check_ts"] = time.time()
    state["last_remote_version"] = release.version
    _save_state(state)

    if not is_newer(release.version, local):
        return UpdateResult(
            status="up_to_date",
            local_version=local,
            remote_version=release.version,
            detail="já está na versão mais recente",
            release=release,
        )

    return UpdateResult(
        status="available",
        local_version=local,
        remote_version=release.version,
        detail=f"nova versão disponível: {release.version}",
        release=release,
    )


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if not str(target).startswith(str(dest) + os.sep) and target != dest:
            raise RuntimeError(f"Entrada zip inválida: {info.filename}")
    zf.extractall(dest)


def download_release(release: ReleaseInfo, dest_dir: Path | None = None) -> tuple[Path, Path]:
    """Baixa e extrai o ZIP. Retorna (pasta_do_pacote, pasta_staging_para_limpar)."""
    if not asset_host_ok(release.download_url):
        raise RuntimeError(f"URL de download não confiável: {release.download_url}")
    staging = Path(dest_dir or tempfile.mkdtemp(prefix="dm-update-"))
    staging.mkdir(parents=True, exist_ok=True)
    zip_path = staging / release.name
    logger.info("Baixando %s…", release.download_url)
    _http_download(release.download_url, zip_path)
    extract_dir = staging / "pkg"
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        _safe_extract(zf, extract_dir)

    for name in (APP_EXE, AGENT_EXE):
        if (extract_dir / name).exists():
            return extract_dir, staging
        hits = list(extract_dir.rglob(name))
        if hits:
            return hits[0].parent, staging
    raise RuntimeError(f"Pacote sem {APP_EXE} / {AGENT_EXE}")


def _write_apply_script(
    package_dir: Path,
    staging_root: Path,
    install_root: Path,
    version: str,
) -> Path:
    temp = Path(os.environ.get("TEMP", tempfile.gettempdir()))
    script = temp / "dm_apply_update.cmd"
    bak = temp / "dm_settings_bak.json"
    settings_src = install_root / "config" / "settings.json"
    app = install_root / APP_EXE
    if not app.exists():
        app = install_root / AGENT_EXE
    restart = f'start "" "{app}" --agent --no-actions'

    # Copia o pacote; restaura settings; reinicia agente sem reaplicar arrumações
    body = f"""@echo off
setlocal
timeout /t 3 /nobreak >nul
taskkill /F /IM {APP_EXE} >nul 2>&1
taskkill /F /IM {AGENT_EXE} >nul 2>&1
taskkill /F /IM {ADMIN_EXE} >nul 2>&1
taskkill /F /IM {SETUP_EXE} >nul 2>&1
timeout /t 2 /nobreak >nul
if exist "{settings_src}" copy /Y "{settings_src}" "{bak}" >nul
robocopy "{package_dir}" "{install_root}" /E /IS /IT /R:2 /W:1 /NFL /NDL /NJH /NJS /nc /ns /np >nul
if exist "{bak}" (
  if not exist "{install_root}\\config" mkdir "{install_root}\\config"
  copy /Y "{bak}" "{settings_src}" >nul
)
> "{install_root}\\VERSION" echo {version}
{restart}
timeout /t 2 /nobreak >nul
rmdir /s /q "{staging_root}" >nul 2>&1
del "%~f0" >nul 2>&1
"""
    script.write_text(body.replace("\n", "\r\n"), encoding="utf-8")
    return script


def schedule_apply(package_dir: Path, staging_root: Path, *, version: str) -> Path:
    install_root = target_install_root()
    install_root.mkdir(parents=True, exist_ok=True)
    script = _write_apply_script(package_dir, staging_root, install_root, version)
    flags = subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags |= subprocess.DETACHED_PROCESS
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=flags, close_fds=True)
    logger.info("Atualização %s agendada via %s → %s", version, script, install_root)
    state = _load_state()
    state["pending_version"] = version
    state["last_apply_ts"] = time.time()
    _save_state(state)
    return script


def download_and_apply(release: ReleaseInfo) -> UpdateResult:
    if not can_apply_update():
        return UpdateResult(
            status="skipped",
            local_version=current_version(),
            remote_version=release.version,
            detail="pacote instalado (.exe) não encontrado — rode INSTALAR primeiro",
            release=release,
        )
    try:
        package_dir, staging = download_release(release)
        schedule_apply(package_dir, staging, version=release.version)
        return UpdateResult(
            status="scheduled",
            local_version=current_version(),
            remote_version=release.version,
            detail="atualização baixada; aplicação agendada (reinício do agente)",
            release=release,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao baixar/aplicar update")
        return UpdateResult(
            status="error",
            local_version=current_version(),
            remote_version=release.version,
            detail=str(exc),
            release=release,
        )


def maybe_auto_update(
    settings: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> UpdateResult:
    """Verifica e, se configurado, baixa/aplica. Retorna status scheduled se o processo deve sair."""
    cfg = _updates_cfg(settings)
    result = check_for_update(settings, force=force)
    if result.status != "available" or result.release is None:
        return result
    if not cfg["auto_apply"] and not force:
        logger.info("Update %s disponível (auto_apply=false)", result.remote_version)
        return result
    applied = download_and_apply(result.release)
    return applied


def release_page_url(repo: str = DEFAULT_REPO) -> str:
    return f"https://github.com/{repo}/releases/latest"


def asset_host_ok(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host.endswith("github.com") or host.endswith("githubusercontent.com")
