# Desktop Manager

[![Build & Release](https://github.com/andersongni/desktop-manager/actions/workflows/build-release.yml/badge.svg)](https://github.com/andersongni/desktop-manager/actions/workflows/build-release.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Software para Windows que automatiza a área de trabalho em segundo plano (no início e no desligamento da sessão).

**Repositório:** [github.com/andersongni/desktop-manager](https://github.com/andersongni/desktop-manager)

## Download (sem Python)

O PC destino **não precisa de Python** nem de outros componentes.

1. Abra a página de [**Releases**](https://github.com/andersongni/desktop-manager/releases)
2. Baixe `desktop-manager-windows-x64-*.zip`
3. Extraia e execute **`INSTALAR`** (assistente gráfico — sem tela preta)
4. Configure com **`ADMINISTRAR.cmd`**

Também é possível baixar o artifact da [aba Actions](https://github.com/andersongni/desktop-manager/actions) (workflow **Build & Release**): o download do Actions já vem como um `.zip` com os arquivos do pacote na raiz (não há zip dentro de zip).

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
| **Plano de fundo** | Só no startup/shutdown: wallpaper 4:3 ou 16:9 conforme a tela |
| **Organizar arquivos** | Só no startup/shutdown: atalhos Word/Excel/PowerPoint/Chrome; move arquivos por tipo |
| **Navegador padrão** | Só no startup/shutdown: abre Configurações do Windows para confirmar |
| **Limpar navegação** | Só no startup/shutdown: cache (cookies/histórico opcionais) |
| **Barra de tarefas** | Só no startup/shutdown: Explorer, Word, Excel, PowerPoint e Chrome |
| **Segundo plano** | Agente residente no logon + tarefa no evento de desligamento |
| **Admin / Instalador** | Painel gráfico e scripts de instalação |

## Conteúdo do pacote ZIP

| Arquivo | Função |
|---------|--------|
| `INSTALAR.vbs` / `.cmd` | Assistente gráfico de instalação |
| `DESINSTALAR.vbs` / `.cmd` | Assistente gráfico de remoção |
| `DesktopManagerSetup.exe` | Wizard (Instalar / Desinstalar) |
| `ADMINISTRAR.cmd` | Painel de configuração |
| `TESTAR_CONFIG.cmd` | Testa a configuração (não aplica arrumações) |
| `DesktopManager*.exe` | Binários (runtime embutido) |
| `config/settings.json` | Configuração |
| `assets/wallpaper/` | `desktop-4x3.jpg` e `desktop-16x9.jpg` |

## Desenvolvimento

### Requisitos (só para desenvolver / gerar o EXE localmente)

- Windows 10/11
- Python 3.10+

```bat
git clone https://github.com/andersongni/desktop-manager.git
cd desktop-manager
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
python main.py test
python main.py install
python main.py uninstall
python main.py status
```

## Configuração

Arquivo: `config/settings.json`

- `wallpaper.auto_aspect` — escolhe 4:3 ou 16:9 pela tela (padrão: true)  
- `wallpaper.image_4x3` / `image_16x9` — imagens padrão da marca  
- `wallpaper.image` — override manual (se `auto_aspect` for false)  
- `organize_desktop.rules` — pasta → extensões  
- `browser.set_default` / `default_browser` — chrome, edge, firefox, brave  
- `browser.clear_data` — cache / cookies / histórico  
- `taskbar.pins` — ordem: `explorer`, `word`, `excel`, `powerpoint`, `chrome`  
- `taskbar.replace` — remove pins padrão e deixa só a lista  

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
- **Barra de tarefas:** usa `LayoutModification.xml` + reinício do Explorer; apps do Office ausentes são ignorados.  
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
└── .github/workflows/      # CI que gera o ZIP para download
```

## Licença

Copyright 2026 Anderson Gni  

Licenciado sob a [Apache License 2.0](LICENSE).
