"""Configuração de logs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from .paths import log_dir


def setup_logging(level: str = "INFO", keep_days: int = 30) -> Path:
    logs = log_dir()
    stamp = datetime.now().strftime("%Y-%m-%d")
    log_file = logs / f"desktop-manager-{stamp}.log"

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    _cleanup_old_logs(logs, keep_days)
    return log_file


def _cleanup_old_logs(folder: Path, keep_days: int) -> None:
    if keep_days <= 0:
        return
    cutoff = datetime.now() - timedelta(days=keep_days)
    for file in folder.glob("desktop-manager-*.log"):
        try:
            if datetime.fromtimestamp(file.stat().st_mtime) < cutoff:
                file.unlink(missing_ok=True)
        except OSError:
            pass
