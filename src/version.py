"""Versão do Desktop Manager (arquivo VERSION do pacote ou fallback)."""

from __future__ import annotations

import json
from pathlib import Path

from . import __version__ as _FALLBACK_VERSION
from .paths import install_dir, project_root


def normalize_version(value: str) -> str:
    return value.strip().lstrip("vV").strip()


def parse_version(value: str) -> tuple[int, ...]:
    """Converte 'v1.2.3' / '1.2.3-beta' em tupla comparável."""
    clean = normalize_version(value)
    parts: list[int] = []
    for chunk in clean.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits or 0))
    return tuple(parts) if parts else (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def read_version_file(root: Path | None = None) -> str | None:
    base = root or project_root()
    for candidate in (base / "VERSION", install_dir() / "VERSION"):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return normalize_version(text)
    return None


def read_install_json_version(root: Path | None = None) -> str | None:
    for base in ((root or project_root()), install_dir()):
        meta = base / "install.json"
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ver = data.get("version")
        if isinstance(ver, str) and ver.strip():
            return normalize_version(ver)
    return None


def current_version(root: Path | None = None) -> str:
    return (
        read_version_file(root)
        or read_install_json_version(root)
        or normalize_version(_FALLBACK_VERSION)
    )
