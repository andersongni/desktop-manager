"""Ponto de entrada do Desktop Manager."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Desktop Manager — automação da área de trabalho no Windows"
    )
    sub = parser.add_subparsers(dest="command")

    p_agent = sub.add_parser("agent", help="Executar agente (segundo plano)")
    p_agent.add_argument("--once", action="store_true")
    p_agent.add_argument(
        "--trigger", choices=["startup", "shutdown", "manual"], default="startup"
    )

    sub.add_parser("admin", help="Abrir painel de administração")

    p_install = sub.add_parser("install", help="Instalar no Windows")
    p_install.add_argument("--use-run-key", action="store_true")

    sub.add_parser("uninstall", help="Desinstalar")
    sub.add_parser("status", help="Status da instalação")
    sub.add_parser("test", help="Testar configuração (sem aplicar arrumações)")

    args = parser.parse_args(argv)

    if args.command == "agent":
        from src.agent import main as agent_main

        return agent_main(["--trigger", args.trigger] + (["--once"] if args.once else []))

    if args.command == "admin" or args.command is None:
        from admin.admin_gui import main as admin_main

        return admin_main()

    if args.command == "install":
        from admin.setup_wizard import main as wizard_main

        return wizard_main(["--wizard", "install"])

    if args.command == "uninstall":
        from admin.setup_wizard import main as wizard_main

        return wizard_main(["--wizard", "uninstall"])

    if args.command == "status":
        from src.installer import main as installer_main

        return installer_main(["--status"])

    if args.command == "test":
        from src.agent import main as agent_main

        return agent_main(["--trigger", "manual", "--once"])

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
