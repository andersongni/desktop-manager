"""Painel gráfico para administrar o Desktop Manager."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Garante import do pacote ao rodar de qualquer cwd
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.actions import run_all  # noqa: E402
from src.config import load_settings, save_settings  # noqa: E402
from src.installer import status  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402
from src.paths import project_root  # noqa: E402
from src.taskbar import DEFAULT_PIN_ORDER, resolve_app_path  # noqa: E402
from src.updater import check_for_update, download_and_apply, maybe_auto_update  # noqa: E402
from src.version import current_version  # noqa: E402
from src.wallpaper import classify_aspect, get_primary_screen_size  # noqa: E402


class AdminApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self._app_version = current_version()
        self.title(f"Desktop Manager — Administração (v{self._app_version})")
        self.geometry("780x620")
        self.minsize(700, 520)
        self.configure(bg="#1e2430")

        self.settings = load_settings()
        setup_logging(
            self.settings.get("logging", {}).get("level", "INFO"),
            self.settings.get("logging", {}).get("keep_days", 30),
        )

        self._style()
        self._build()
        self._load_into_form()
        self._refresh_status()

    def _style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#1e2430")
        style.configure("TLabel", background="#1e2430", foreground="#e8ecf1")
        style.configure("TCheckbutton", background="#1e2430", foreground="#e8ecf1")
        style.configure("TNotebook", background="#1e2430")
        style.configure("TNotebook.Tab", padding=[12, 6])
        style.configure("Header.TLabel", font=("Segoe UI Semibold", 16), foreground="#f0f3f7")
        style.configure("Muted.TLabel", foreground="#9aa3b2")
        style.configure("Accent.TButton", padding=8)

    def _build(self) -> None:
        header = ttk.Frame(self, padding=16)
        header.pack(fill="x")
        ttk.Label(
            header,
            text=f"Desktop Manager  v{self._app_version}",
            style="Header.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Configure ações, instale o agente e execute em segundo plano",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        self.status_var = tk.StringVar(value="Status: …")
        ttk.Label(header, textvariable=self.status_var, style="Muted.TLabel").pack(
            anchor="w", pady=(8, 0)
        )

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.tab_general = ttk.Frame(nb, padding=12)
        self.tab_wallpaper = ttk.Frame(nb, padding=12)
        self.tab_organize = ttk.Frame(nb, padding=12)
        self.tab_browser = ttk.Frame(nb, padding=12)
        self.tab_taskbar = ttk.Frame(nb, padding=12)
        self.tab_install = ttk.Frame(nb, padding=12)

        nb.add(self.tab_general, text="Geral")
        nb.add(self.tab_wallpaper, text="Plano de fundo")
        nb.add(self.tab_organize, text="Organizar")
        nb.add(self.tab_browser, text="Navegador")
        nb.add(self.tab_taskbar, text="Barra de tarefas")
        nb.add(self.tab_install, text="Instalar")

        self._build_general()
        self._build_wallpaper()
        self._build_organize()
        self._build_browser()
        self._build_taskbar()
        self._build_install()

        footer = ttk.Frame(self, padding=16)
        footer.pack(fill="x")
        ttk.Button(footer, text="Salvar configuração", command=self.save).pack(side="left")
        ttk.Button(footer, text="Testar configuração", command=self.test_config).pack(
            side="left", padx=8
        )
        ttk.Button(footer, text="Recarregar", command=self.reload).pack(side="left")

        self.log = tk.Text(
            self,
            height=8,
            bg="#12161e",
            fg="#c5ccd6",
            insertbackground="#fff",
            relief="flat",
            font=("Consolas", 9),
        )
        self.log.pack(fill="both", padx=16, pady=(0, 16))

    def _build_general(self) -> None:
        self.var_enabled = tk.BooleanVar()
        self.var_on_startup = tk.BooleanVar()
        self.var_on_shutdown = tk.BooleanVar()
        ttk.Checkbutton(self.tab_general, text="Ativar Desktop Manager", variable=self.var_enabled).pack(
            anchor="w"
        )
        ttk.Checkbutton(
            self.tab_general, text="Executar ao iniciar o Windows (logon)", variable=self.var_on_startup
        ).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            self.tab_general, text="Executar ao desligar / encerrar sessão", variable=self.var_on_shutdown
        ).pack(anchor="w", pady=4)
        ttk.Label(
            self.tab_general,
            text=(
                "O agente fica em segundo plano após o logon e escuta o desligamento.\n"
                "Plano de fundo, organização, barra de tarefas e limpeza do navegador\n"
                "só são aplicados no início ou no fim da sessão — nunca durante o uso."
            ),
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(12, 0))

        ttk.Separator(self.tab_general).pack(fill="x", pady=12)
        ttk.Label(self.tab_general, text="Atualizações (GitHub Releases)").pack(anchor="w")
        self.var_updates_enabled = tk.BooleanVar()
        self.var_updates_auto_apply = tk.BooleanVar()
        ttk.Checkbutton(
            self.tab_general,
            text="Verificar novas versões automaticamente",
            variable=self.var_updates_enabled,
        ).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(
            self.tab_general,
            text="Baixar e instalar atualizações automaticamente",
            variable=self.var_updates_auto_apply,
        ).pack(anchor="w")
        row_up = ttk.Frame(self.tab_general)
        row_up.pack(fill="x", pady=(8, 0))
        ttk.Button(row_up, text="Verificar agora", command=self.check_updates).pack(side="left")
        ttk.Button(row_up, text="Atualizar agora", command=self.apply_updates).pack(side="left", padx=8)
        self.update_status_var = tk.StringVar(value="")
        ttk.Label(
            self.tab_general,
            textvariable=self.update_status_var,
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(8, 0))

    def _build_wallpaper(self) -> None:
        self.var_wp_enabled = tk.BooleanVar()
        self.var_wp_auto = tk.BooleanVar(value=True)
        self.var_wp_4x3 = tk.StringVar()
        self.var_wp_16x9 = tk.StringVar()
        self.var_wp_path = tk.StringVar()
        self.var_wp_style = tk.StringVar()
        self.var_wp_screen = tk.StringVar(value="")

        ttk.Checkbutton(
            self.tab_wallpaper, text="Alterar plano de fundo", variable=self.var_wp_enabled
        ).pack(anchor="w")
        ttk.Checkbutton(
            self.tab_wallpaper,
            text="Escolher automaticamente 4:3 ou 16:9 conforme a tela",
            variable=self.var_wp_auto,
            command=self._toggle_wp_auto,
        ).pack(anchor="w", pady=(4, 8))

        try:
            w, h = get_primary_screen_size()
            self.var_wp_screen.set(f"Tela atual: {w}×{h} → {classify_aspect(w, h)}")
        except OSError:
            self.var_wp_screen.set("Tela atual: (não detectada)")
        ttk.Label(self.tab_wallpaper, textvariable=self.var_wp_screen, style="Muted.TLabel").pack(
            anchor="w"
        )

        row4 = ttk.Frame(self.tab_wallpaper)
        row4.pack(fill="x", pady=(10, 4))
        ttk.Label(row4, text="4:3:").pack(side="left")
        ttk.Entry(row4, textvariable=self.var_wp_4x3, width=55).pack(side="left", padx=8)
        ttk.Button(row4, text="…", width=3, command=lambda: self._browse_wp_into(self.var_wp_4x3)).pack(
            side="left"
        )

        row16 = ttk.Frame(self.tab_wallpaper)
        row16.pack(fill="x", pady=4)
        ttk.Label(row16, text="16:9:").pack(side="left")
        ttk.Entry(row16, textvariable=self.var_wp_16x9, width=55).pack(side="left", padx=8)
        ttk.Button(
            row16, text="…", width=3, command=lambda: self._browse_wp_into(self.var_wp_16x9)
        ).pack(side="left")

        self.row_forced = ttk.Frame(self.tab_wallpaper)
        self.row_forced.pack(fill="x", pady=4)
        ttk.Label(self.row_forced, text="Forçar:").pack(side="left")
        ttk.Entry(self.row_forced, textvariable=self.var_wp_path, width=55).pack(side="left", padx=8)
        ttk.Button(
            self.row_forced, text="…", width=3, command=lambda: self._browse_wp_into(self.var_wp_path)
        ).pack(side="left")

        row2 = ttk.Frame(self.tab_wallpaper)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="Estilo:").pack(side="left")
        ttk.Combobox(
            row2,
            textvariable=self.var_wp_style,
            values=["fill", "fit", "stretch", "center", "tile", "span"],
            width=12,
            state="readonly",
        ).pack(side="left", padx=8)
        ttk.Label(
            self.tab_wallpaper,
            text="Aplicado automaticamente só no início ou desligamento da sessão.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(12, 0))
        self._toggle_wp_auto()

    def _build_organize(self) -> None:
        self.var_org_enabled = tk.BooleanVar()
        self.var_remove_other_shortcuts = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self.tab_organize,
            text="Organizar área de trabalho automaticamente",
            variable=self.var_org_enabled,
        ).pack(anchor="w")
        ttk.Checkbutton(
            self.tab_organize,
            text="Remover atalhos, exceto Word, Excel, PowerPoint e Chrome",
            variable=self.var_remove_other_shortcuts,
        ).pack(anchor="w", pady=4)
        ttk.Label(
            self.tab_organize,
            text=(
                "Arquivos vão para Documentos, Imagens, Vídeos (e Músicas/Downloads)\n"
                "conforme a extensão. Atalhos permitidos permanecem na Desktop.\n\n"
                "Importante: a arrumação só roda no início ou no desligamento da sessão.\n"
                "Não é executada durante o uso (nem em \"Testar configuração\")."
            ),
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(8, 0))

    def _build_browser(self) -> None:
        self.var_ensure_installed = tk.BooleanVar()
        self.var_set_default = tk.BooleanVar()
        self.var_default_browser = tk.StringVar()
        self.var_clear_enabled = tk.BooleanVar()
        self.var_clear_cache = tk.BooleanVar()
        self.var_clear_cookies = tk.BooleanVar()
        self.var_clear_history = tk.BooleanVar()

        ttk.Checkbutton(
            self.tab_browser,
            text="Instalar Google Chrome automaticamente se não estiver presente",
            variable=self.var_ensure_installed,
        ).pack(anchor="w")
        ttk.Checkbutton(
            self.tab_browser,
            text="Definir como navegador padrão (abre Configurações do Windows se necessário)",
            variable=self.var_set_default,
        ).pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(self.tab_browser)
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Navegador:").pack(side="left")
        ttk.Combobox(
            row,
            textvariable=self.var_default_browser,
            values=["chrome", "edge", "firefox", "brave"],
            width=14,
            state="readonly",
        ).pack(side="left", padx=8)
        ttk.Label(
            self.tab_browser,
            text=(
                "Se o Chrome não estiver instalado, o Desktop Manager baixa o instalador "
                "oficial e conclui a instalação em modo silencioso no início/desligamento "
                "da sessão. No Windows 10/11 a confirmação final do navegador padrão "
                "pode exigir um clique nas Configurações."
            ),
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(0, 4))
        ttk.Separator(self.tab_browser).pack(fill="x", pady=12)
        ttk.Checkbutton(
            self.tab_browser, text="Limpar dados de navegação", variable=self.var_clear_enabled
        ).pack(anchor="w")
        ttk.Checkbutton(self.tab_browser, text="Cache", variable=self.var_clear_cache).pack(anchor="w")
        ttk.Checkbutton(self.tab_browser, text="Cookies", variable=self.var_clear_cookies).pack(anchor="w")
        ttk.Checkbutton(self.tab_browser, text="Histórico", variable=self.var_clear_history).pack(anchor="w")
        ttk.Label(
            self.tab_browser,
            text=(
                "Cookies/histórico desativados por padrão.\n"
                "A limpeza só ocorre no início ou desligamento da sessão — nunca durante o uso."
            ),
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(8, 0))

    def _build_taskbar(self) -> None:
        self.var_tb_enabled = tk.BooleanVar()
        self.var_tb_replace = tk.BooleanVar(value=True)
        self.tb_pins: list[str] = list(DEFAULT_PIN_ORDER)

        ttk.Checkbutton(
            self.tab_taskbar,
            text="Aplicar layout da barra de tarefas no fluxo automático",
            variable=self.var_tb_enabled,
        ).pack(anchor="w")
        ttk.Checkbutton(
            self.tab_taskbar,
            text="Substituir pins padrão (somente os listados abaixo)",
            variable=self.var_tb_replace,
        ).pack(anchor="w", pady=(4, 8))
        ttk.Label(
            self.tab_taskbar,
            text="Ordem fixa (esquerda → direita): Explorer, Word, Excel, PowerPoint, Chrome",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w")

        self.pin_list = tk.Listbox(self.tab_taskbar, height=6, bg="#12161e", fg="#e8ecf1")
        self.pin_list.pack(fill="x", pady=8)

        row = ttk.Frame(self.tab_taskbar)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="Atualizar status dos apps", command=self._refresh_tb_pins).pack(side="left")
        ttk.Label(
            self.tab_taskbar,
            text=(
                "O layout da barra só é aplicado no início ou desligamento da sessão.\n"
                "(Pode reiniciar o Explorer nesses momentos.)"
            ),
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(8, 0))

    def _build_install(self) -> None:
        ttk.Label(
            self.tab_install,
            text="Instala o agente em %LOCALAPPDATA%\\DesktopManager e registra logon/desligamento.",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w")
        row = ttk.Frame(self.tab_install)
        row.pack(fill="x", pady=12)
        ttk.Button(row, text="Instalar", command=self._install).pack(side="left")
        ttk.Button(row, text="Desinstalar", command=self._uninstall).pack(side="left", padx=8)
        ttk.Button(row, text="Atualizar status", command=self._refresh_status).pack(side="left")
        ttk.Button(row, text="Abrir pasta do projeto", command=self._open_project).pack(side="left", padx=8)

        self.install_info = tk.Text(
            self.tab_install, height=12, bg="#12161e", fg="#c5ccd6", relief="flat", font=("Consolas", 9)
        )
        self.install_info.pack(fill="both", expand=True, pady=(8, 0))

    # --- helpers UI ---

    def _log(self, msg: str) -> None:
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _load_into_form(self) -> None:
        s = self.settings
        self.var_enabled.set(s.get("enabled", True))
        self.var_on_startup.set(s.get("triggers", {}).get("on_startup", True))
        self.var_on_shutdown.set(s.get("triggers", {}).get("on_shutdown", True))

        up = s.get("updates", {})
        self.var_updates_enabled.set(up.get("enabled", True))
        self.var_updates_auto_apply.set(up.get("auto_apply", True))

        wp = s.get("wallpaper", {})
        self.var_wp_enabled.set(wp.get("enabled", True))
        self.var_wp_auto.set(wp.get("auto_aspect", True))
        self.var_wp_4x3.set(wp.get("image_4x3", "assets/wallpaper/desktop-4x3.jpg"))
        self.var_wp_16x9.set(wp.get("image_16x9", "assets/wallpaper/desktop-16x9.jpg"))
        self.var_wp_path.set(wp.get("image", ""))
        self.var_wp_style.set(wp.get("style", "fill"))
        self._toggle_wp_auto()

        org = s.get("organize_desktop", {})
        self.var_org_enabled.set(org.get("enabled", True))
        self.var_remove_other_shortcuts.set(org.get("remove_other_shortcuts", True))

        br = s.get("browser", {})
        self.var_ensure_installed.set(br.get("ensure_installed", True))
        self.var_set_default.set(br.get("set_default", True))
        self.var_default_browser.set(br.get("default_browser", "chrome"))
        cd = br.get("clear_data", {})
        self.var_clear_enabled.set(cd.get("enabled", True))
        self.var_clear_cache.set(cd.get("clear_cache", True))
        self.var_clear_cookies.set(cd.get("clear_cookies", False))
        self.var_clear_history.set(cd.get("clear_history", False))

        tb = s.get("taskbar", {})
        self.var_tb_enabled.set(tb.get("enabled", True))
        self.var_tb_replace.set(tb.get("replace", True))
        pins = tb.get("pins") or list(DEFAULT_PIN_ORDER)
        self.tb_pins = list(pins)
        self._refresh_tb_pins()

    def _form_to_settings(self) -> dict:
        s = self.settings
        s["enabled"] = self.var_enabled.get()
        s.setdefault("triggers", {})
        s["triggers"]["on_startup"] = self.var_on_startup.get()
        s["triggers"]["on_shutdown"] = self.var_on_shutdown.get()

        s.setdefault("updates", {})
        s["updates"]["enabled"] = self.var_updates_enabled.get()
        s["updates"]["auto_apply"] = self.var_updates_auto_apply.get()
        s["updates"].setdefault("check_interval_hours", 6)
        s["updates"].setdefault("github_repo", "andersongni/desktop-manager")

        s.setdefault("wallpaper", {})
        s["wallpaper"]["enabled"] = self.var_wp_enabled.get()
        s["wallpaper"]["auto_aspect"] = self.var_wp_auto.get()
        s["wallpaper"]["image_4x3"] = self.var_wp_4x3.get().strip()
        s["wallpaper"]["image_16x9"] = self.var_wp_16x9.get().strip()
        s["wallpaper"]["image"] = self.var_wp_path.get().strip()
        s["wallpaper"]["style"] = self.var_wp_style.get()

        s.setdefault("organize_desktop", {})
        s["organize_desktop"]["enabled"] = self.var_org_enabled.get()
        s["organize_desktop"]["remove_other_shortcuts"] = self.var_remove_other_shortcuts.get()
        s["organize_desktop"]["keep_shortcuts"] = ["word", "excel", "powerpoint", "chrome"]

        s.setdefault("browser", {})
        s["browser"]["ensure_installed"] = self.var_ensure_installed.get()
        s["browser"]["set_default"] = self.var_set_default.get()
        s["browser"]["default_browser"] = self.var_default_browser.get()
        s["browser"].setdefault("clear_data", {})
        s["browser"]["clear_data"]["enabled"] = self.var_clear_enabled.get()
        s["browser"]["clear_data"]["clear_cache"] = self.var_clear_cache.get()
        s["browser"]["clear_data"]["clear_cookies"] = self.var_clear_cookies.get()
        s["browser"]["clear_data"]["clear_history"] = self.var_clear_history.get()

        s.setdefault("taskbar", {})
        s["taskbar"]["enabled"] = self.var_tb_enabled.get()
        s["taskbar"]["replace"] = self.var_tb_replace.get()
        s["taskbar"]["pins"] = list(self.tb_pins)
        return s

    def save(self) -> None:
        self.settings = self._form_to_settings()
        path = save_settings(self.settings)
        self._log(f"Configuração salva: {path}")
        messagebox.showinfo("Salvo", f"Configuração salva em:\n{path}")

    def reload(self) -> None:
        self.settings = load_settings()
        self._load_into_form()
        self._log("Configuração recarregada")

    def test_config(self) -> None:
        """Valida a configuração sem aplicar arrumações (só startup/shutdown as aplicam)."""
        self.settings = self._form_to_settings()
        save_settings(self.settings)

        def work() -> None:
            report = run_all(self.settings, trigger="manual")
            self.after(0, lambda: self._log(json.dumps(report, ensure_ascii=False, indent=2)))
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Teste",
                    "Configuração testada.\n"
                    "Arrumações de ambiente ficam como 'skipped' — "
                    "só rodam no início/desligamento.\nVeja o log abaixo.",
                ),
            )

        self._log("Testando configuração (sem alterar o ambiente)…")
        threading.Thread(target=work, daemon=True).start()

    def _toggle_wp_auto(self) -> None:
        state = "disabled" if self.var_wp_auto.get() else "normal"
        for child in self.row_forced.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    def _browse_wp_into(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Escolher imagem",
            filetypes=[("Imagens", "*.jpg;*.jpeg;*.png;*.bmp"), ("Todos", "*.*")],
        )
        if path:
            var.set(path)

    def _refresh_tb_pins(self) -> None:
        self.pin_list.delete(0, "end")
        labels = {
            "explorer": "1. Windows Explorer",
            "word": "2. Microsoft Word",
            "excel": "3. Microsoft Excel",
            "powerpoint": "4. Microsoft PowerPoint",
            "chrome": "5. Google Chrome",
        }
        for app_id in self.tb_pins:
            path = resolve_app_path(app_id)
            status = str(path) if path else "NÃO ENCONTRADO"
            label = labels.get(app_id, app_id)
            self.pin_list.insert("end", f"{label}  —  {status}")

    def _install(self) -> None:
        self._open_setup_wizard("install")

    def _uninstall(self) -> None:
        self._open_setup_wizard("uninstall")

    def _open_setup_wizard(self, mode: str) -> None:
        """Abre o assistente gráfico (sem console)."""
        try:
            from admin.setup_wizard import SetupWizard

            wiz = SetupWizard(initial_mode=mode)
            wiz.transient(self)
            self.wait_window(wiz)
            self._refresh_status()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro", str(exc))

    def _refresh_status(self) -> None:
        info = status()
        self.status_var.set(
            f"v{info.get('version', self._app_version)} | "
            f"Instalado: {'sim' if info['installed'] else 'não'} | "
            f"Run: {'sim' if info['run_key'] else 'não'} | "
            f"Tarefas: {', '.join(info['tasks']) or 'nenhuma'}"
        )
        self.install_info.delete("1.0", "end")
        self.install_info.insert("end", json.dumps(info, indent=2, ensure_ascii=False))

    def check_updates(self) -> None:
        self.settings = self._form_to_settings()
        save_settings(self.settings)
        self.update_status_var.set("Consultando GitHub…")

        def work() -> None:
            result = check_for_update(self.settings, force=True)
            msg = (
                f"{result.status}: local {result.local_version}"
                + (f" → remota {result.remote_version}" if result.remote_version else "")
                + (f" — {result.detail}" if result.detail else "")
            )

            def done() -> None:
                self.update_status_var.set(msg)
                self._log(msg)
                if result.status == "available":
                    messagebox.showinfo(
                        "Atualização",
                        f"Nova versão {result.remote_version} disponível "
                        f"(atual: {result.local_version}).\n"
                        "Use «Atualizar agora» ou aguarde o próximo logon.",
                    )
                elif result.status == "up_to_date":
                    messagebox.showinfo("Atualização", "Você já está na versão mais recente.")
                elif result.status == "error":
                    messagebox.showerror("Atualização", result.detail or "Falha ao verificar")

            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def apply_updates(self) -> None:
        self.settings = self._form_to_settings()
        save_settings(self.settings)
        if not messagebox.askyesno(
            "Atualizar",
            "Baixar a versão mais recente do GitHub e instalar agora?\n"
            "O agente será reiniciado. Sua configuração será preservada.",
        ):
            return
        self.update_status_var.set("Baixando atualização…")

        def work() -> None:
            result = maybe_auto_update(self.settings, force=True)
            if result.status == "available" and result.release is not None:
                result = download_and_apply(result.release)
            msg = f"{result.status}: {result.detail}"

            def done() -> None:
                self.update_status_var.set(msg)
                self._log(msg)
                if result.status == "scheduled":
                    messagebox.showinfo(
                        "Atualização",
                        f"Versão {result.remote_version} baixada.\n"
                        "A aplicação será reiniciada em instantes.",
                    )
                    self.after(800, self.destroy)
                elif result.status == "up_to_date":
                    messagebox.showinfo("Atualização", "Nada a atualizar.")
                elif result.status == "skipped":
                    messagebox.showwarning("Atualização", result.detail or "Atualização ignorada")
                else:
                    messagebox.showerror("Atualização", result.detail or "Falha")

            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _open_project(self) -> None:
        subprocess.Popen(["explorer", str(project_root())])


def main() -> int:
    app = AdminApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
