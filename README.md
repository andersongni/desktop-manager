# Desktop Manager

[![Build & Release](https://github.com/andersongni/desktop-manager/actions/workflows/build-release.yml/badge.svg)](https://github.com/andersongni/desktop-manager/actions/workflows/build-release.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Software para Windows que automatiza a área de trabalho em segundo plano (no início e no desligamento da sessão).

**Repositório:** [github.com/andersongni/desktop-manager](https://github.com/andersongni/desktop-manager)

## Download (sem Python)

O PC destino **não precisa de Python** nem de outros componentes.

1. Abra a página de [**Releases**](https://github.com/andersongni/desktop-manager/releases)
2. Baixe `desktop-manager-windows-x64-*.zip`
3. Extraia e execute **`INSTALAR.cmd`**
4. Configure com **`ADMINISTRAR.cmd`**

Também é possível baixar o artifact da [aba Actions](https://github.com/andersongni/desktop-manager/actions) (workflow **Build & Release**).

### Publicar uma nova versão

```bash
git tag v1.0.0
git push origin v1.0.0
```

O GitHub Actions gera o `.exe`, empacota o ZIP e publica no Release automaticamente.

Ou use **Actions → Build & Release → Run workflow** com `create_release=true` e a versão desejada.

## O que faz

| Função | Descrição |
|--------|-----------|
| **Plano de fundo** | Define wallpaper a partir de uma imagem do projeto |
| **Organizar arquivos** | Move itens da Desktop para Documentos, Imagens, Vídeos, Músicas, Downloads |
| **Navegador padrão** | Abre as Configurações do Windows para você confirmar o navegador |
| **Limpar navegação** | Remove cache (e opcionalmente cookies/histórico) do Chrome, Edge, Firefox, Brave |
| **Barra de tarefas** | Tenta fixar/desafixar atalhos (desafixar costuma funcionar; fixar pode ser bloqueado pelo Windows) |
| **Segundo plano** | Agente residente no logon + tarefa no evento de desligamento |
| **Admin / Instalador** | Painel gráfico e scripts de instalação |

## Conteúdo do pacote ZIP

| Arquivo | Função |
|---------|--------|
| `INSTALAR.cmd` | Instala e registra início/desligamento |
| `DESINSTALAR.cmd` | Remove |
| `ADMINISTRAR.cmd` | Painel de configuração |
| `EXECUTAR_AGORA.cmd` | Roda as ações uma vez |
| `DesktopManager*.exe` | Binários (runtime embutido) |
| `config/settings.json` | Configuração |
| `assets/wallpaper/` | Imagem de fundo |

## Ambiente de testes (Vagrant)

VM **Windows 11** com **Google Chrome** para validar o app sem mexer no host:

```powershell
cd test\vagrant
vagrant up
```

Detalhes em [`test/README.md`](test/README.md).

## Desenvolvimento

### Requisitos (só para desenvolver / gerar o EXE localmente)

- Windows 10/11
- Python 3.10+

```bat
git clone https://github.com/andersongni/desktop-manager.git
cd desktop-manager
python scripts\make_wallpaper.py
python main.py admin
```

Gerar o pacote localmente:

```bat
pip install -r requirements-build.txt
python scripts\build_release.py
```

Saída: `release\DesktopManager\`

### CLI

```bat
python main.py admin
python main.py run
python main.py install
python main.py uninstall
python main.py status
```

## Configuração

Arquivo: `config/settings.json`

- `wallpaper.image` — caminho da imagem  
- `organize_desktop.rules` — pasta → extensões  
- `browser.set_default` / `default_browser` — chrome, edge, firefox, brave  
- `browser.clear_data` — cache / cookies / histórico  
- `taskbar.pin` / `taskbar.unpin` — caminhos de `.exe` ou `.lnk`  
- `triggers.on_startup` / `on_shutdown`  

## Como funciona a instalação

1. Copia o pacote para `%LOCALAPPDATA%\DesktopManager`
2. Cria tarefas no Agendador:
   - `DesktopManager\Startup` — no logon
   - `DesktopManager\Shutdown` — no desligamento
3. Cria atalhos no Menu Iniciar → **Desktop Manager**
4. Se o Agendador falhar, usa a chave `HKCU\...\Run`

Logs em `logs/desktop-manager-AAAA-MM-DD.log`.

## Limitações do Windows

- **Navegador padrão:** a Microsoft exige confirmação manual nas Configurações.
- **Fixar na barra de tarefas:** APIs de pin foram restringidas no Windows 10/11; desafixar normalmente funciona.
- **Limpeza de dados:** feche o navegador antes; arquivos em uso são ignorados.

## Estrutura

```
desktop-manager/
├── main.py
├── entry_*.py              # entradas PyInstaller
├── config/settings.json
├── assets/wallpaper/
├── src/                    # núcleo
├── admin/admin_gui.py
├── scripts/build_release.py
├── test/vagrant/           # IaC: Windows 11 + Chrome (Vagrant)
└── .github/workflows/      # CI que gera o ZIP para download
```

## Licença

Copyright 2026 Anderson Gni  

Licenciado sob a [Apache License 2.0](LICENSE).
