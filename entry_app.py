"""Entrada unificada — wizard, agente (bandeja), admin e CLI.

DesktopManager.exe (standalone):
  (sem args)              → assistente se não instalado; senão inicia na bandeja
  --wizard [install|…]    → assistente navegável (instalar / atualizar / remover)
  --agent                 → agente em segundo plano com ícone na bandeja
  --admin                 → painel de configuração
  --cli --install|…       → instalação via linha de comando
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _has_flag(args: list[str], *names: str) -> bool:
    return any(a in names for a in args)


def _consume_wizard_mode(args: list[str]) -> str | None:
    if "--wizard" in args:
        idx = args.index("--wizard")
        if idx + 1 < len(args) and args[idx + 1] in ("install", "uninstall", "update"):
            return args[idx + 1]
        return "auto"
    if _has_flag(args, "--install") or "install" in args:
        return "install"
    if _has_flag(args, "--uninstall") or "uninstall" in args:
        return "uninstall"
    if _has_flag(args, "--update") or "update" in args:
        return "update"
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    if "--cli" in args:
        cleaned = [a for a in args if a != "--cli"]
        from src.installer import main as installer_main

        return installer_main(cleaned)

    if _has_flag(args, "--admin", "admin"):
        from admin.admin_gui import main as admin_main

        return admin_main()

    wizard_mode = _consume_wizard_mode(args)
    if wizard_mode is not None:
        from admin.setup_wizard import main as wizard_main

        wargs = ["--wizard", wizard_mode] if wizard_mode != "auto" else ["--wizard"]
        return wizard_main(wargs)

    # Agente explícito (startup / shutdown / bandeja)
    if _has_flag(args, "--agent") or _has_flag(args, "--trigger", "--once", "--no-actions"):
        from src.agent import main as agent_main

        cleaned = [a for a in args if a != "--agent"]
        # Compatibilidade: pacotes antigos usavam só --trigger sem --agent
        return agent_main(cleaned)

    # Duplo clique / execução padrão
    from src.installer import status

    info = status()
    if info.get("installed"):
        from src.agent import main as agent_main

        # Já instalado: sobe na bandeja sem reaplicar arrumações do logon
        return agent_main(["--trigger", "manual", "--no-actions"])

    from admin.setup_wizard import main as wizard_main

    return wizard_main(["--wizard", "install"])


if __name__ == "__main__":
    raise SystemExit(main())
