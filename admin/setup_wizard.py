"""Assistente gráfico de instalação / atualização / desinstalação (sem console)."""

from __future__ import annotations

import io
import logging
import subprocess
import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app_icon import apply_window_icon  # noqa: E402
from src.installer import install, status, uninstall  # noqa: E402
from src.runtime import app_executable, is_frozen  # noqa: E402
from src.version import current_version  # noqa: E402


class _UiLogHandler(logging.Handler):
    def __init__(self, append_fn) -> None:
        super().__init__()
        self._append = append_fn

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._append(self.format(record))
        except Exception:  # noqa: BLE001
            pass


class SetupWizard(tk.Tk):
    def __init__(self, initial_mode: str | None = None) -> None:
        super().__init__()
        self.title("Desktop Manager — Assistente")
        self.geometry("580x460")
        self.minsize(540, 400)
        self.configure(bg="#f4f6f8")
        self.resizable(False, False)
        apply_window_icon(self)

        self.mode = initial_mode if initial_mode in ("install", "uninstall", "update") else None
        # Atalhos diretos abrem na confirmação
        self.step = 2 if self.mode else 0
        self._busy = False
        self._launch_after = True

        self._style()
        self._build_shell()
        self._show_step()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Wizard.TFrame", background="#f4f6f8")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Wizard.TLabel", background="#f4f6f8", foreground="#1c2430")
        style.configure("Card.TLabel", background="#ffffff", foreground="#1c2430")
        style.configure("Muted.TLabel", background="#ffffff", foreground="#5c6775")
        style.configure("Title.TLabel", background="#ffffff", foreground="#0f1720", font=("Segoe UI Semibold", 16))
        style.configure("Header.TLabel", background="#1e3a5f", foreground="#ffffff", font=("Segoe UI Semibold", 12))
        style.configure("HeaderBar.TFrame", background="#1e3a5f")
        style.configure("Nav.TFrame", background="#e8edf2")
        style.configure("Accent.TButton", padding=(14, 8))

    def _build_shell(self) -> None:
        header = ttk.Frame(self, style="HeaderBar.TFrame", padding=(20, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Desktop Manager", style="Header.TLabel").pack(anchor="w")
        self.subtitle = ttk.Label(
            header,
            text="Assistente de instalação e atualização",
            background="#1e3a5f",
            foreground="#c5d4e8",
            font=("Segoe UI", 9),
        )
        self.subtitle.pack(anchor="w", pady=(2, 0))

        self.body = ttk.Frame(self, style="Wizard.TFrame", padding=20)
        self.body.pack(fill="both", expand=True)

        self.card = ttk.Frame(self.body, style="Card.TFrame", padding=20)
        self.card.pack(fill="both", expand=True)

        nav = ttk.Frame(self, style="Nav.TFrame", padding=(16, 12))
        nav.pack(fill="x", side="bottom")
        self.btn_back = ttk.Button(nav, text="Voltar", command=self._back)
        self.btn_back.pack(side="left")
        self.btn_cancel = ttk.Button(nav, text="Cancelar", command=self._on_close)
        self.btn_cancel.pack(side="right")
        self.btn_next = ttk.Button(nav, text="Avançar", style="Accent.TButton", command=self._next)
        self.btn_next.pack(side="right", padx=(0, 8))

    def _clear_card(self) -> None:
        for child in self.card.winfo_children():
            child.destroy()

    def _show_step(self) -> None:
        self._clear_card()
        if self.step == 0:
            self._page_welcome()
        elif self.step == 1:
            self._page_action()
        elif self.step == 2:
            self._page_confirm()
        elif self.step == 3:
            self._page_progress()
        else:
            self._page_done()

    def _page_welcome(self) -> None:
        self.subtitle.configure(text="Bem-vindo")
        ttk.Label(self.card, text="Bem-vindo", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.card,
            text=(
                "Este assistente instala, atualiza ou remove o Desktop Manager.\n"
                "Um único executável standalone — não é necessário ter Python.\n\n"
                "Após instalar, o programa fica na área de notificação (bandeja),\n"
                "com atalho para configurações, inicialização com o Windows e sair."
            ),
            style="Muted.TLabel",
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

        info = status()
        status_txt = (
            f"Versão do pacote: v{current_version()}  ·  "
            f"Situação: {'instalado' if info.get('installed') else 'não instalado'}"
            f"  ·  Autostart: {'sim' if info.get('run_key') or info.get('tasks') else 'não'}"
        )
        ttk.Label(self.card, text=status_txt, style="Muted.TLabel").pack(anchor="w", pady=(18, 0))

        self.btn_back.configure(state="disabled")
        self.btn_next.configure(text="Avançar", state="normal")
        self.btn_cancel.configure(state="normal")

    def _page_action(self) -> None:
        self.subtitle.configure(text="Escolha a ação")
        ttk.Label(self.card, text="O que deseja fazer?", style="Title.TLabel").pack(anchor="w")

        info = status()
        default = self.mode or ("update" if info.get("installed") else "install")
        self.action_var = tk.StringVar(value=default)

        ttk.Radiobutton(
            self.card,
            text="Instalar o Desktop Manager",
            variable=self.action_var,
            value="install",
        ).pack(anchor="w", pady=(16, 4))
        ttk.Label(
            self.card,
            text="Copia os arquivos, registra início com o Windows e cria atalhos.",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=(22, 0))

        ttk.Radiobutton(
            self.card,
            text="Atualizar / reparar instalação",
            variable=self.action_var,
            value="update",
        ).pack(anchor="w", pady=(12, 4))
        ttk.Label(
            self.card,
            text="Reinstala os arquivos e mantém a configuração (settings.json).",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=(22, 0))

        ttk.Radiobutton(
            self.card,
            text="Desinstalar o Desktop Manager",
            variable=self.action_var,
            value="uninstall",
        ).pack(anchor="w", pady=(12, 4))
        ttk.Label(
            self.card,
            text="Remove tarefas, atalhos e a pasta de instalação.",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=(22, 0))

        self.btn_back.configure(state="normal")
        self.btn_next.configure(text="Avançar", state="normal")

    def _page_confirm(self) -> None:
        if hasattr(self, "action_var"):
            self.mode = self.action_var.get()
        mode = self.mode or "install"
        self.subtitle.configure(text="Confirmação")

        if mode in ("install", "update"):
            title = "Confirmar instalação" if mode == "install" else "Confirmar atualização"
            ttk.Label(self.card, text=title, style="Title.TLabel").pack(anchor="w")
            ttk.Label(
                self.card,
                text=(
                    "O Desktop Manager será instalado/atualizado em:\n"
                    "%LOCALAPPDATA%\\DesktopManager\n\n"
                    "Serão criados atalhos no Menu Iniciar e o ícone ficará\n"
                    "disponível na área de notificação após a conclusão."
                ),
                style="Muted.TLabel",
                justify="left",
            ).pack(anchor="w", pady=(12, 0))
            self._launch_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                self.card,
                text="Iniciar o Desktop Manager ao concluir (ícone na bandeja)",
                variable=self._launch_var,
            ).pack(anchor="w", pady=(16, 0))
            self.btn_next.configure(text="Instalar" if mode == "install" else "Atualizar")
        else:
            ttk.Label(self.card, text="Confirmar desinstalação", style="Title.TLabel").pack(anchor="w")
            ttk.Label(
                self.card,
                text=(
                    "Isso remove o Desktop Manager deste usuário:\n"
                    "• tarefas agendadas e chave de inicialização\n"
                    "• atalhos do Menu Iniciar\n"
                    "• pasta %LOCALAPPDATA%\\DesktopManager\n\n"
                    "Seus documentos e arquivos pessoais não são apagados."
                ),
                style="Muted.TLabel",
                justify="left",
            ).pack(anchor="w", pady=(12, 0))
            self.btn_next.configure(text="Desinstalar")

        self.btn_back.configure(state="normal")
        self.btn_cancel.configure(state="normal")

    def _page_progress(self) -> None:
        mode = self.mode or "install"
        labels = {
            "install": ("Instalando…", "Instalando…"),
            "update": ("Atualizando…", "Atualizando…"),
            "uninstall": ("Removendo…", "Desinstalando…"),
        }
        sub, title = labels.get(mode, ("Processando…", "Processando…"))
        self.subtitle.configure(text=sub)
        ttk.Label(self.card, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self.card,
            text="Aguarde. Não feche esta janela.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(8, 12))

        self.progress = ttk.Progressbar(self.card, mode="indeterminate")
        self.progress.pack(fill="x")
        self.progress.start(12)

        self.log = tk.Text(
            self.card,
            height=10,
            bg="#0f1720",
            fg="#d7dee8",
            relief="flat",
            font=("Consolas", 9),
            state="disabled",
        )
        self.log.pack(fill="both", expand=True, pady=(12, 0))

        self.btn_back.configure(state="disabled")
        self.btn_next.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")

        threading.Thread(target=self._run_action, daemon=True).start()

    def _page_done(self) -> None:
        ok = getattr(self, "_result_ok", False)
        mode = self.mode or "install"
        self.subtitle.configure(text="Concluído")
        if ok:
            titles = {
                "install": "Instalação concluída",
                "update": "Atualização concluída",
                "uninstall": "Desinstalação concluída",
            }
            title = titles.get(mode, "Concluído")
            if mode in ("install", "update"):
                detail = (
                    "O Desktop Manager está pronto.\n"
                    "Use o ícone na área de notificação (bandeja) para configurar,\n"
                    "definir a inicialização com o Windows ou encerrar o programa."
                )
            else:
                detail = "O Desktop Manager foi removido deste computador."
        else:
            title = "Algo deu errado"
            detail = "Veja os detalhes abaixo. Você pode fechar e tentar novamente."

        ttk.Label(self.card, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.card, text=detail, style="Muted.TLabel", justify="left").pack(
            anchor="w", pady=(10, 12)
        )

        summary = tk.Text(
            self.card,
            height=10,
            bg="#0f1720",
            fg="#d7dee8",
            relief="flat",
            font=("Consolas", 9),
        )
        summary.pack(fill="both", expand=True)
        summary.insert("end", getattr(self, "_result_log", ""))
        summary.configure(state="disabled")

        self.btn_back.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.btn_next.configure(text="Concluir", state="normal")

    def _append_log(self, line: str) -> None:
        def ui() -> None:
            if not hasattr(self, "log") or not self.log.winfo_exists():
                return
            self.log.configure(state="normal")
            self.log.insert("end", line.rstrip() + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")

        self.after(0, ui)

    def _run_action(self) -> None:
        self._busy = True
        mode = self.mode or "install"
        if hasattr(self, "_launch_var"):
            self._launch_after = bool(self._launch_var.get())
        buf = io.StringIO()
        handler = _UiLogHandler(self._append_log)
        handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
        root_logger = logging.getLogger()
        prev_level = root_logger.level
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

        ok = False
        try:
            with redirect_stdout(buf):
                if mode in ("install", "update"):
                    install(use_tasks=True)
                else:
                    uninstall()
            ok = True
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"ERROR | {exc}")
            ok = False
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(prev_level)
            self._busy = False

        text = buf.getvalue()
        if text.strip():
            for line in text.splitlines():
                self._append_log(line)

        def finish() -> None:
            if hasattr(self, "progress") and self.progress.winfo_exists():
                self.progress.stop()
            self._result_ok = ok
            try:
                self._result_log = self.log.get("1.0", "end").strip()
            except tk.TclError:
                self._result_log = text
            if not ok:
                messagebox.showerror("Erro", "A operação não foi concluída. Veja o log no assistente.")
            elif ok and mode in ("install", "update") and self._launch_after:
                self._launch_agent()
            self.step = 4
            self._show_step()

        self.after(0, finish)

    def _launch_agent(self) -> None:
        try:
            from src.paths import install_dir

            root = install_dir() if install_dir().exists() else ROOT
            if is_frozen() or (root / "DesktopManager.exe").exists():
                exe = app_executable(root)
                subprocess.Popen(
                    [exe, "--agent", "--no-actions"],
                    cwd=str(root),
                    close_fds=True,
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(ROOT / "entry_app.py"), "--agent", "--no-actions"],
                    cwd=str(ROOT),
                    close_fds=True,
                )
            self._append_log("INFO | Desktop Manager iniciado na bandeja")
        except OSError as exc:
            self._append_log(f"WARNING | Não iniciou a bandeja: {exc}")

    def _next(self) -> None:
        if self._busy:
            return
        if self.step == 0:
            self.step = 1 if self.mode is None else 2
        elif self.step == 1:
            self.mode = self.action_var.get()
            self.step = 2
        elif self.step == 2:
            self.step = 3
        elif self.step >= 4:
            self.destroy()
            return
        self._show_step()

    def _back(self) -> None:
        if self._busy or self.step <= 0:
            return
        if self.step == 2 and self.mode and not hasattr(self, "action_var"):
            self.mode = None
            self.step = 0
        else:
            self.step -= 1
        self._show_step()

    def _on_close(self) -> None:
        if self._busy:
            messagebox.showinfo("Aguarde", "A operação ainda está em andamento.")
            return
        self.destroy()


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    mode = None
    if "--wizard" in args:
        idx = args.index("--wizard")
        if idx + 1 < len(args) and args[idx + 1] in ("install", "uninstall", "update"):
            mode = args[idx + 1]
    if "--install" in args or "install" in args:
        if "--cli" not in args:
            mode = mode or "install"
    if "--uninstall" in args or "uninstall" in args:
        if "--cli" not in args:
            mode = mode or "uninstall"
    if "--update" in args or "update" in args:
        if "--cli" not in args:
            mode = mode or "update"

    app = SetupWizard(initial_mode=mode)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
