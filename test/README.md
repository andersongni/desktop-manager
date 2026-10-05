# Ambiente de testes (IaC / Vagrant)

Sobe uma **VM Windows 11** com **Google Chrome** para validar o Desktop Manager sem alterar o seu PC principal.

## Pré-requisitos (host)

| Ferramenta | Observação |
|------------|------------|
| [Vagrant](https://developer.hashicorp.com/vagrant/install) ≥ 2.3 | obrigatório |
| [VirtualBox](https://www.virtualbox.org/) ≥ 7 | padrão |
| Hyper-V | alternativa no Windows Pro/Enterprise |
| ≥ 8 GB RAM livre | a VM usa 8 GB por padrão |
| VT-x / AMD-V | virtualização habilitada na BIOS |

> O download da box Windows 11 tem vários GB na primeira execução.

## Subir a VM

```powershell
cd test\vagrant
vagrant up
```

Ou:

```powershell
.\scripts\up.ps1
```

Login padrão da box: **`vagrant` / `vagrant`**

- Janela gráfica do VirtualBox abre automaticamente (`vb.gui = true`)
- RDP: `vagrant rdp` (porta host `13389`)

## O que a IaC instala

1. **Chocolatey** + 7-Zip + Notepad++
2. **Google Chrome** (`choco install googlechrome`, com fallback do instalador oficial)
3. Arquivos de amostra na Desktop (para testar o organizador)
4. Atalhos para `C:\desktop-manager` e, se existir, o `INSTALAR.cmd` do release

## Testar o Desktop Manager na VM

No **host**, gere o pacote (se ainda não tiver):

```powershell
python scripts\build_release.py
```

Na **VM**:

1. Abra o atalho **Instalar Desktop Manager** (ou `C:\desktop-manager\release\DesktopManager\INSTALAR.cmd`)
2. Configure com `ADMINISTRAR.cmd`
3. Use `EXECUTAR_AGORA.cmd` e confira se os arquivos de amostra foram movidos

O projeto inteiro fica sincronizado em **`C:\desktop-manager`**.

## Comandos úteis

```powershell
cd test\vagrant

vagrant status          # estado
vagrant provision       # reinstala Chrome / recria amostras
vagrant reload          # reinicia a VM
vagrant halt            # desliga
vagrant destroy -f      # apaga a VM

.\scripts\status.ps1
.\scripts\provision.ps1
.\scripts\destroy.ps1
```

### Recursos da VM

```powershell
$env:DM_VM_MEMORY = "12288"   # MB
$env:DM_VM_CPUS   = "4"
vagrant up
```

### Hyper-V em vez de VirtualBox

```powershell
$env:VAGRANT_DEFAULT_PROVIDER = "hyperv"
vagrant up --provider=hyperv
```

## Estrutura

```
test/
├── README.md
├── workspace/              # pasta sincronizada gravável (C:\dm-test)
└── vagrant/
    ├── Vagrantfile         # IaC da VM
    ├── provision/
    │   ├── 01-base.ps1     # Chocolatey + ferramentas
    │   ├── 02-chrome.ps1   # Google Chrome
    │   └── 03-ready.ps1    # Desktop de teste + atalhos
    └── scripts/
        ├── up.ps1
        ├── destroy.ps1
        ├── status.ps1
        └── provision.ps1
```

## Box

- Nome: [`gusztavvargadr/windows-11`](https://portal.cloud.hashicorp.com/vagrant/discover/gusztavvargadr/windows-11)
- Communicator: WinRM
- Credenciais: `vagrant` / `vagrant`
