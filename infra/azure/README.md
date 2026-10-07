# Azure IaC — VM de teste (free tier)

Sobe uma **Windows Server 2022** pequena na Azure para testar o Desktop Manager (instalar, startup/shutdown, auto-update) via RDP.

## O que é criado

| Recurso | Detalhe |
|---------|---------|
| VM | `Standard_D2s_v4` (fallback se série B sem cota; free trial prefere `Standard_B2ats_v2`) |
| SO | **Windows 11 Pro 24H2** pt-BR (Trusted Launch / Gen2; Language Pack no bootstrap) |
| Disco | Standard SSD 128 GB |
| Rede | VNet + NSG (RDP 3389) + IP público estático |
| Auto-shutdown | Todo dia às **22:00** (Brasília) com **deallocate** |
| Bootstrap | Baixa a última release do GitHub em `C:\DesktopManager-release` |

> Contas free **novas** incluem crédito + horas B2ats/B2ts/B2pts v2.  
> Windows **não é “sempre grátis”** forever — use auto-shutdown e `destroy.ps1` quando terminar.  
> Se o SKU não existir na região, troque (`-VmSize Standard_B2ts_v2` ou `Standard_B1s`).

## Pré-requisitos

1. Conta Azure com **subscription ativa** (Free Trial / Pay-as-you-go)
2. [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
3. Este repositório já no GitHub em `main` (o bootstrap baixa `infra/azure/bootstrap.ps1` via raw URL)

### Subscription free — não dá para criar pela IaC

A Microsoft **não permite** criar a primeira subscription Free Trial via Bicep/ARM/CLI.
Isso só no portal (cartão + MFA):

1. https://azure.microsoft.com/free/
2. Ou: https://portal.azure.com → **Subscriptions** → **Add**

Depois que a subscription existir, **toda a VM de teste** sobe só com a IaC (`.\deploy.ps1`).

Criar subscription *extra* por API (`Microsoft.Subscription/aliases`) só funciona se você já tiver conta de cobrança MCA/EA com `billingScope` — não cobre Free Trial novo.

## Subir

No PowerShell:

```powershell
cd infra\azure
.\deploy.ps1
```

O deploy **não pede senha**: gera conta local (`dmadmin`), aplica auto-logon na VM, registra a credencial no Credential Manager do seu PC e abre o RDP sem prompt. Use `-OpenRdp:$false` para não abrir o cliente.

Opções:

```powershell
# Região / tamanho
.\deploy.ps1 -Location brazilsouth -VmSize Standard_B2ats_v2

# Restringir RDP ao seu IP (padrão: detecta via ipify)
.\deploy.ps1 -AllowedRdpSource '203.0.113.10/32'

# Sem baixar a release automaticamente
.\deploy.ps1 -SkipBootstrap
```

Ao final o script mostra o **IP** e o comando `mstsc`.

## Testar o Desktop Manager

1. Conecte por RDP (`mstsc /v:<ip>`) com o usuário `dmadmin`
2. Abra `C:\DesktopManager-release` (atalho no Desktop público)
3. Execute **INSTALAR** → **ADMINISTRAR**
4. Reinicie a sessão/VM para validar startup
5. Para auto-update: publique uma tag `vX.Y.Z` nova e use **Atualizar agora** / próximo logon

## Parar / destruir (economia)

```powershell
# Só deallocate (mantém disco; compute para de cobrar)
az vm deallocate -g rg-desktop-manager-test -n dmtest-vm

# Ligar de novo
az vm start -g rg-desktop-manager-test -n dmtest-vm

# Apagar TUDO
.\destroy.ps1
```

## Deploy manual (az)

```powershell
az group create -n rg-desktop-manager-test -l eastus
az deployment group create `
  -g rg-desktop-manager-test `
  -f main.bicep `
  --parameters adminPassword='SuaSenhaForte!123' vmSize=Standard_B2ats_v2
```

## SKUs free-friendly

| SKU | Notas |
|-----|--------|
| `Standard_B2ats_v2` | **Padrão** — AMD, free trial Windows |
| `Standard_B2ts_v2` | Intel |
| `Standard_B2pts_v2` | Arm (nem todas imagens Windows) |
| `Standard_B1s` / `B2s` | Série antiga; pode estar indisponível |

Se o deploy falhar com “SkuNotAvailable”, mude `-Location` ou `-VmSize`.
