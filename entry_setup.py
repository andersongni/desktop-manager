"""Entrada PyInstaller — assistente gráfico (ou CLI com --cli)."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    # Automação / scripts: --cli --install | --uninstall | --status
    if "--cli" in args:
        cleaned = [a for a in args if a != "--cli"]
        from src.installer import main as installer_main

        return installer_main(cleaned)

    # Padrão: wizard gráfico (sem janela preta)
    from admin.setup_wizard import main as wizard_main

    return wizard_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
