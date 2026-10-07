"""Entrada legada do agente — redireciona para o app unificado."""

from __future__ import annotations

import sys

from entry_app import main


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--agent" not in args and not any(a.startswith("--trigger") for a in args):
        args = ["--agent", *args]
    elif "--agent" not in args:
        args = ["--agent", *args]
    raise SystemExit(main(args))
