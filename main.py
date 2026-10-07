"""Ponto de entrada do Desktop Manager (desenvolvimento)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entry_app import main as app_main


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    # Atalhos de desenvolvimento: python main.py admin|install|…
    if args and args[0] in ("admin", "install", "uninstall", "status", "test", "agent", "wizard"):
        cmd = args[0]
        rest = args[1:]
        mapping = {
            "admin": ["--admin"],
            "install": ["--wizard", "install"],
            "uninstall": ["--wizard", "uninstall"],
            "wizard": ["--wizard", *rest] if rest else ["--wizard"],
            "agent": ["--agent", *rest],
            "test": ["--agent", "--trigger", "manual", "--once"],
            "status": ["--cli", "--status"],
        }
        if cmd == "wizard" and rest:
            return app_main(["--wizard", *rest])
        return app_main(mapping[cmd])
    return app_main(args)


if __name__ == "__main__":
    sys.exit(main())
