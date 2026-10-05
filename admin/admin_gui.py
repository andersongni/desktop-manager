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
from src.browser import clear_browsing_data, find_browser_exe, set_default_browser  # noqa: E402
from src.config import load_settings, save_settings  # noqa: E402
from src.installer import install, status, uninstall  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402
from src.organizer import organize_desktop  # noqa: E402
from src.paths import project_root, resolve_asset  # noqa: E402
from src.taskbar import pin, unpin  # noqa: E402
from src.wallpaper import set_wallpaper  # noqa: E402


class AdminApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Desktop Manager — Administração")
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
        ttk.Label(header, text="Desktop Manager", style="Header.TLabel").pack(anchor="w")
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
        ttk.Button(footer, text="Executar agora", command=self.run_now).pack(side="left", padx=8)
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
            text="O agente fica em segundo plano após o logon e escuta o desligamento.",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(12, 0))

    def _build_wallpaper(self) -> None:
        self.var_wp_enabled = tk.BooleanVar()
        self.var_wp_path = tk.StringVar()
        self.var_wp_style = tk.StringVar()
        ttk.Checkbutton(
            self.tab_wallpaper, text="Alterar plano de fundo", variable=self.var_wp_enabled
        ).pack(anchor="w")
        row = ttk.Frame(self.tab_wallpaper)
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="Imagem:").pack(side="left")
        ttk.Entry(row, textvariable=self.var_wp_path, width=60).pack(side="left", padx=8)
        ttk.Button(row, text="Procurar…", command=self._browse_wallpaper).pack(side="left")
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
        ttk.Button(self.tab_wallpaper, text="Aplicar agora", command=self._apply_wallpaper).pack(
            anchor="w", pady=12
        )

    def _build_organize(self) -> None:
        self.var_org_enabled = tk.BooleanVar()
        self.var_leave_shortcuts = tk.BooleanVar()
        ttk.Checkbutton(
            self.tab_organize,
            text="Mover arquivos da área de trabalho para Documentos, Imagens, etc.",
            variable=self.var_org_enabled,
        ).pack(anchor="w")
        ttk.Checkbutton(
            self.tab_organize, text="Manter atalhos (.lnk) na área de trabalho", variable=self.var_leave_shortcuts
        ).pack(anchor="w", pady=4)
        ttk.Label(
            self.tab_organize,
            text="Regras por extensão ficam em config/settings.json (abaixo um resumo ao salvar).",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(8, 0))
        ttk.Button(self.tab_organize, text="Organizar agora", command=self._organize_now).pack(
            anchor="w", pady=12
        )

    def _build_browser(self) -> None:
        self.var_set_default = tk.BooleanVar()
        self.var_default_browser = tk.StringVar()
        self.var_clear_enabled = tk.BooleanVar()
        self.var_clear_cache = tk.BooleanVar()
        self.var_clear_cookies = tk.BooleanVar()
        self.var_clear_history = tk.BooleanVar()

        ttk.Checkbutton(
            self.tab_browser,
            text="Solicitar definição do navegador padrão (abre Configurações do Windows)",
            variable=self.var_set_default,
        ).pack(anchor="w")
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
        ttk.Button(row, text="Abrir Configurações", command=self._set_default_now).pack(side="left")

        ttk.Separator(self.tab_browser).pack(fill="x", pady=12)
        ttk.Checkbutton(
            self.tab_browser, text="Limpar dados de navegação", variable=self.var_clear_enabled
        ).pack(anchor="w")
        ttk.Checkbutton(self.tab_browser, text="Cache", variable=self.var_clear_cache).pack(anchor="w")
        ttk.Checkbutton(self.tab_browser, text="Cookies", variable=self.var_clear_cookies).pack(anchor="w")
        ttk.Checkbutton(self.tab_browser, text="Histórico", variable=self.var_clear_history).pack(anchor="w")
        ttk.Label(
            self.tab_browser,
            text="Feche o navegador antes de limpar. Cookies/histórico desativados por padrão.",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(8, 0))
        ttk.Button(self.tab_browser, text="Limpar agora", command=self._clear_now).pack(anchor="w", pady=12)

    def _build_taskbar(self) -> None:
        self.var_tb_enabled = tk.BooleanVar()
        ttk.Checkbutton(
            self.tab_taskbar, text="Aplicar pin/unpin no fluxo automático", variable=self.var_tb_enabled
        ).pack(anchor="w")
        ttk.Label(
            self.tab_taskbar,
            text="No Windows 10/11, fixar por API pode ser bloqueado; desafixar costuma funcionar.",
            style="Muted.TLabel",
            wraplength=640,
        ).pack(anchor="w", pady=(4, 8))

        self.pin_list = tk.Listbox(self.tab_taskbar, height=5, bg="#12161e", fg="#e8ecf1")
        self.pin_list.pack(fill="x")
        row = ttk.Frame(self.tab_taskbar)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="Adicionar para fixar…", command=lambda: self._add_tb("pin")).pack(side="left")
        ttk.Button(row, text="Remover da lista", command=lambda: self._remove_tb("pin")).pack(
            side="left", padx=6
        )
        ttk.Button(row, text="Fixar selecionado agora", command=self._pin_now).pack(side="left")

        ttk.Label(self.tab_taskbar, text="Desafixar:").pack(anchor="w", pady=(12, 0))
        self.unpin_list = tk.Listbox(self.tab_taskbar, height=5, bg="#12161e", fg="#e8ecf1")
        self.unpin_list.pack(fill="x")
        row2 = ttk.Frame(self.tab_taskbar)
        row2.pack(fill="x", pady=4)
        ttk.Button(row2, text="Adicionar para desafixar…", command=lambda: self._add_tb("unpin")).pack(
            side="left"
        )
        ttk.Button(row2, text="Remover da lista", command=lambda: self._remove_tb("unpin")).pack(
            side="left", padx=6
        )
        ttk.Button(row2, text="Desafixar selecionado agora", command=self._unpin_now).pack(side="left")

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

        wp = s.get("wallpaper", {})
        self.var_wp_enabled.set(wp.get("enabled", True))
        self.var_wp_path.set(wp.get("image", "assets/wallpaper/desktop.jpg"))
        self.var_wp_style.set(wp.get("style", "fill"))

        org = s.get("organize_desktop", {})
        self.var_org_enabled.set(org.get("enabled", True))
        self.var_leave_shortcuts.set(org.get("leave_shortcuts", True))

        br = s.get("browser", {})
        self.var_set_default.set(br.get("set_default", False))
        self.var_default_browser.set(br.get("default_browser", "chrome"))
        cd = br.get("clear_data", {})
        self.var_clear_enabled.set(cd.get("enabled", True))
        self.var_clear_cache.set(cd.get("clear_cache", True))
        self.var_clear_cookies.set(cd.get("clear_cookies", False))
        self.var_clear_history.set(cd.get("clear_history", False))

        tb = s.get("taskbar", {})
        self.var_tb_enabled.set(tb.get("enabled", False))
        self.pin_list.delete(0, "end")
        self.unpin_list.delete(0, "end")
        for p in tb.get("pin", []):
            self.pin_list.insert("end", p)
        for p in tb.get("unpin", []):
            self.unpin_list.insert("end", p)

    def _form_to_settings(self) -> dict:
        s = self.settings
        s["enabled"] = self.var_enabled.get()
        s.setdefault("triggers", {})
        s["triggers"]["on_startup"] = self.var_on_startup.get()
        s["triggers"]["on_shutdown"] = self.var_on_shutdown.get()

        s.setdefault("wallpaper", {})
        s["wallpaper"]["enabled"] = self.var_wp_enabled.get()
        s["wallpaper"]["image"] = self.var_wp_path.get().strip()
        s["wallpaper"]["style"] = self.var_wp_style.get()

        s.setdefault("organize_desktop", {})
        s["organize_desktop"]["enabled"] = self.var_org_enabled.get()
        s["organize_desktop"]["leave_shortcuts"] = self.var_leave_shortcuts.get()

        s.setdefault("browser", {})
        s["browser"]["set_default"] = self.var_set_default.get()
        s["browser"]["default_browser"] = self.var_default_browser.get()
        s["browser"].setdefault("clear_data", {})
        s["browser"]["clear_data"]["enabled"] = self.var_clear_enabled.get()
        s["browser"]["clear_data"]["clear_cache"] = self.var_clear_cache.get()
        s["browser"]["clear_data"]["clear_cookies"] = self.var_clear_cookies.get()
        s["browser"]["clear_data"]["clear_history"] = self.var_clear_history.get()

        s.setdefault("taskbar", {})
        s["taskbar"]["enabled"] = self.var_tb_enabled.get()
        s["taskbar"]["pin"] = list(self.pin_list.get(0, "end"))
        s["taskbar"]["unpin"] = list(self.unpin_list.get(0, "end"))
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

    def run_now(self) -> None:
        self.settings = self._form_to_settings()
        save_settings(self.settings)

        def work() -> None:
            report = run_all(self.settings, trigger="manual")
            self.after(0, lambda: self._log(json.dumps(report, ensure_ascii=False, indent=2)))
            self.after(0, lambda: messagebox.showinfo("Concluído", "Fluxo executado. Veja o log abaixo."))

        self._log("Executando fluxo completo…")
        threading.Thread(target=work, daemon=True).start()

    def _browse_wallpaper(self) -> None:
        path = filedialog.askopenfilename(
            title="Escolher imagem",
            filetypes=[("Imagens", "*.jpg;*.jpeg;*.png;*.bmp"), ("Todos", "*.*")],
        )
        if path:
            self.var_wp_path.set(path)

    def _apply_wallpaper(self) -> None:
        try:
            image = resolve_asset(self.var_wp_path.get().strip())
            set_wallpaper(image, self.var_wp_style.get())
            self._log(f"Plano de fundo aplicado: {image}")
            messagebox.showinfo("OK", "Plano de fundo aplicado.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro", str(exc))

    def _organize_now(self) -> None:
        self.settings = self._form_to_settings()
        moved = organize_desktop(self.settings.get("organize_desktop", {}))
        self._log(f"Organizados: {len(moved)} arquivo(s)")
        messagebox.showinfo("OK", f"{len(moved)} arquivo(s) movido(s).")

    def _set_default_now(self) -> None:
        name = self.var_default_browser.get()
        if find_browser_exe(name) is None:
            messagebox.showerror("Erro", f"Navegador '{name}' não encontrado.")
            return
        result = set_default_browser(name)
        self._log(json.dumps(result, ensure_ascii=False))
        messagebox.showinfo(
            "Configurações",
            result.get("message", "Abra as Configurações e confirme o navegador padrão."),
        )

    def _clear_now(self) -> None:
        self.settings = self._form_to_settings()
        if not messagebox.askyesno("Confirmar", "Limpar dados de navegação agora?"):
            return
        report = clear_browsing_data(self.settings["browser"]["clear_data"])
        self._log(json.dumps(report, ensure_ascii=False, indent=2))
        messagebox.showinfo("OK", "Limpeza concluída. Veja o log.")

    def _add_tb(self, which: str) -> None:
        path = filedialog.askopenfilename(
            title="Selecionar .exe ou .lnk",
            filetypes=[("Atalhos/Apps", "*.lnk;*.exe"), ("Todos", "*.*")],
        )
        if not path:
            return
        box = self.pin_list if which == "pin" else self.unpin_list
        box.insert("end", path)

    def _remove_tb(self, which: str) -> None:
        box = self.pin_list if which == "pin" else self.unpin_list
        sel = box.curselection()
        if sel:
            box.delete(sel[0])

    def _pin_now(self) -> None:
        sel = self.pin_list.curselection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um item na lista de fixar.")
            return
        report = pin(self.pin_list.get(sel[0]))
        self._log(json.dumps(report, ensure_ascii=False))
        messagebox.showinfo("Resultado", report.get("detail", report.get("status")))

    def _unpin_now(self) -> None:
        sel = self.unpin_list.curselection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um item na lista de desafixar.")
            return
        report = unpin(self.unpin_list.get(sel[0]))
        self._log(json.dumps(report, ensure_ascii=False))
        messagebox.showinfo("Resultado", report.get("detail", report.get("status")))

    def _install(self) -> None:
        def work() -> None:
            try:
                root = install(use_tasks=True)
                self.after(0, lambda: self._log(f"Instalado em {root}"))
                self.after(0, self._refresh_status)
                self.after(0, lambda: messagebox.showinfo("Instalado", f"Instalado em:\n{root}"))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: messagebox.showerror("Erro", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _uninstall(self) -> None:
        if not messagebox.askyesno("Confirmar", "Desinstalar o Desktop Manager?"):
            return

        def work() -> None:
            try:
                uninstall()
                self.after(0, lambda: self._log("Desinstalado"))
                self.after(0, self._refresh_status)
                self.after(0, lambda: messagebox.showinfo("OK", "Desinstalado."))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: messagebox.showerror("Erro", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _refresh_status(self) -> None:
        info = status()
        self.status_var.set(
            f"Instalado: {'sim' if info['installed'] else 'não'} | "
            f"Run: {'sim' if info['run_key'] else 'não'} | "
            f"Tarefas: {', '.join(info['tasks']) or 'nenhuma'}"
        )
        self.install_info.delete("1.0", "end")
        self.install_info.insert("end", json.dumps(info, indent=2, ensure_ascii=False))

    def _open_project(self) -> None:
        subprocess.Popen(["explorer", str(project_root())])


def main() -> int:
    app = AdminApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
